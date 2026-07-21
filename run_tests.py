import subprocess
with open("test_output.txt", "w") as f:
    subprocess.run(["python", "-m", "pytest", "tests"], stdout=f, stderr=subprocess.STDOUT)
