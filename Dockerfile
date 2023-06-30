# base image
FROM python:3.10

# install git, since it is required by DVC
RUN apt update && apt install git -y

# set some Python env variables
ENV PYTHONDONOTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# set the working directory to the home directory
WORKDIR /srv/www/lyprox

# upgrade pip and setuptools
RUN pip install --upgrade pip setuptools

# copy the requirements file to the WORKDIR directory
COPY requirements.txt .

# install the requirements
RUN pip install -r requirements.txt

# copy the repo content to the WORKDIR directory
COPY . .

# install LyProX
RUN pip install .
