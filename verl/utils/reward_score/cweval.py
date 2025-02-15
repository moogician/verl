from pathlib import Path
from time import sleep
import docker, shutil, tarfile, io, json
from docker.models.containers import Container

client = docker.from_env()
# need to start a container from here for testing

def start_container():
        ret = client.containers.run(  
            "co1lin/cweval",
            'zsh',
            detach=True,
            tty=True,
            stdout=True,
            stderr=True,
            network_mode="host",
        )
        
        try:
            while ret.status != "running":
                sleep(1)
                ret.reload()
        except Exception as e:
            raise RuntimeError("Container start error", e)

        exit_code, result = ret.exec_run(['zsh', '-c', r"sed -i '62a \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ \ max_tokens=100000,' cweval/ai.py"])
        assert exit_code == 0, result
        exit_code, result = ret.exec_run(['zsh', '-c', r"sed -i '97s/only_first/only_last/g' cweval/evaluate.py"])
        assert exit_code == 0, result
        exit_code, result = ret.exec_run(['zsh', '-c', r"sed -i '212s/if only_last:/if only_last and len(code_blocks) > 0:/' cweval/commons.py"])
        assert exit_code == 0, result
        return ret

container: Container = start_container()

def copy_to_container(container, folder, dest):
    try:
        # Create a tar archive of the source folder
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tar.add(folder, arcname=".")
        
        # Seek to the beginning of the stream
        tar_stream.seek(0)
        
        # Copy the tar archive to the container and extract it
        container.put_archive(dest, tar_stream)
        container.exec_run(["sudo", "chown", "-R", "ubuntu", dest])

    except Exception as e:
        print(f"Error: {e}")

def read_from_container(container, file_path):
    # Retrieve the file as a tar archive
    stream, stat = container.get_archive(file_path)

    # Read the tar archive
    tar_bytes = io.BytesIO(b"".join(stream))

    # Extract the file content
    with tarfile.open(fileobj=tar_bytes, mode="r") as tar:
        file_member = tar.getmember(file_path.lstrip("/"))  # Remove leading slash
        file_content = tar.extractfile(file_member).read().decode("utf-8") # type: ignore
    return file_content

def recreate(d: Path):
    shutil.rmtree(d)
    d.mkdir(parents=True)

def compute_score(solution_str, ground_truth) -> float:
    # prepare docker env WARNING: check closer what's the proper path for evaluation
    tmp_dir = Path("evals")
    recreate(tmp_dir)
    #"benchmark/lang/c/cwe_119_0_c_task.c"
    save_path = tmp_dir / "generated_0" / (ground_truth['file_path'].replace("_task", "_raw"))
    save_path.parent.mkdir(parents=True)
    with open(save_path, "w") as f:
        f.write(solution_str)

    # delete previous evals folder in docker
    container.exec_run("sudo rm -rf /home/ubuntu/CWEval/evals/")
    copy_to_container(container, tmp_dir, "/home/ubuntu/CWEval/evals/")

    # run eval in the docker
    command = "source ~/.zshrc && source .env && python cweval/evaluate.py pipeline --eval_path evals --docker False"
    container.exec_run(command)
    res = json.loads(read_from_container(container, "evals/res_all.json"))
    assert len(res) == 1
    func_secure = next(res.values())['func_secure'][0]
    functional = next(res.values())['functional'][0]
    secure = next(res.values())['secure'][0]
    return 1 if func_secure else 0.5*functional # TODO: change this later

