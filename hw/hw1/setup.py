from setuptools import setup, find_packages

setup(
    name="interstellar-dnn-mapping",
    version="0.1.dev0",
    author="Kartik Prabhu",
    author_email="kprabhu7@stanford.edu",
    description="Design space exploration for DNN accelerators",
    long_description=open("README.md", "r", encoding="utf-8").read(),
    package_dir={"": "src"},
    packages=find_packages("src"),
)
