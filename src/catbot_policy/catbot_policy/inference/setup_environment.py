"""Prepare independent CPU or Jetson CUDA policy environments on the target host."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from catbot_policy.configuration import inference_python


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--python", default="auto")
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--uv", default="uv")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--torch-wheel", help="Path or URL to a trusted JetPack-compatible Torch wheel"
    )
    source.add_argument(
        "--system-site-packages",
        action="store_true",
        help="Reuse CUDA Torch already installed for the selected base Python",
    )
    args = parser.parse_args()
    cuda = args.device == "cuda"
    if cuda and not (args.torch_wheel or args.system_site_packages):
        parser.error("CUDA requires --torch-wheel or --system-site-packages")
    if not cuda and (args.torch_wheel or args.system_site_packages):
        parser.error(
            "CPU uses the locked project; CUDA package sources are not applicable"
        )
    project = Path(__file__).resolve().parent
    environment = (
        (args.environment or project / (".venv-cuda" if cuda else ".venv"))
        .expanduser()
        .resolve()
    )
    selected_python = (
        "/usr/bin/python3"
        if args.system_site_packages and args.python == "auto"
        else inference_python(args.device, args.python)
    )
    env = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT"):
        env.pop(key, None)
    env["UV_PROJECT_ENVIRONMENT"] = str(environment)

    def run(*command):
        subprocess.run(command, env=env, check=True)

    interpreter = environment / "bin/python"
    if cuda:
        if not environment.exists():
            run(
                args.uv,
                "venv",
                "--python",
                selected_python,
                *(["--system-site-packages"] if args.system_site_packages else []),
                str(environment),
            )
        elif not interpreter.is_file():
            parser.error(f"Existing environment has no Python: {environment}")
        if args.system_site_packages:
            config = (environment / "pyvenv.cfg").read_text().lower()
            if "include-system-site-packages = true" not in config:
                parser.error("Use a new environment path for --system-site-packages")
        if args.torch_wheel:
            # Never resolve torch from PyPI or apply the CPU project's lock here.
            run(
                args.uv,
                "pip",
                "install",
                "--python",
                str(interpreter),
                "numpy>=1.26,<2",
                args.torch_wheel,
            )
    else:
        run(
            args.uv,
            "sync",
            "--locked",
            "--project",
            str(project),
            "--python",
            selected_python,
        )
    # Target-only diagnostic: no ROS, policy, camera, motors or simulation is started.
    diagnostic = (
        "import sys, torch; "
        "print('Python:', sys.version.split()[0]); "
        "print('PyTorch:', torch.__version__); "
        "print('CUDA build:', torch.version.cuda); "
    )
    if cuda:
        diagnostic += (
            "assert torch.cuda.is_available(), 'No usable CUDA in this environment'; "
            "print('GPU:', torch.cuda.get_device_name(0)); "
            "torch.zeros(1, device='cuda'); torch.cuda.synchronize(); "
        )
    # uv also checks that a pre-existing environment matches --python.
    run(
        args.uv,
        "run",
        "--no-sync",
        "--project",
        str(project / "cuda" if cuda else project),
        "--python",
        selected_python,
        "python",
        "-c",
        diagnostic,
    )
    print(f"Prepared {args.device} policy environment: {environment}", flush=True)


if __name__ == "__main__":
    main()
