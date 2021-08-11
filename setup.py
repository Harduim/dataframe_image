import setuptools


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="df_img",
    version="0.0.1",
    author="Arthur Harduim",
    author_email="harduim.arthur@gmail.com",
    description="Convert DataFrames as images",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="jupyter notebook pandas dataframe image pdf markdown",
    url="https://github.com/Harduim/dataframe_image",
    packages=setuptools.find_packages(),
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=["pandas>=1.1.5", "nbconvert>=5", "matplotlib>=3.1", "beautifulsoup4"],
    include_package_data=True,
)
