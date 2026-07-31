import subprocess

# !! THIS MUST RUN IN THE ROOT DIRECTORY OF THE BOT, NOT THE utils/ DIRECTORY!!

GIT_UPDATE_SRC = "https://github.com/SatanModding/SenshaBot"
GIT_UPGRADE_CMD = [
    "fetch",
    "pull",
]


def upgrade():
    for cmd in GIT_UPGRADE_CMD:
        print(f"running command: git {cmd} {GIT_UPDATE_SRC}\n")
        result = subprocess.run(["git", cmd, GIT_UPDATE_SRC], capture_output=True)
        text = result.stdout if result.stdout else result.stderr

        print(text.decode())


upgrade()
