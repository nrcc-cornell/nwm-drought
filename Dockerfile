FROM python:3.12-slim

RUN apt update; apt install -y curl
RUN curl -L -O https://github.com/bnoon/tired-manager/releases/download/v1.1/tired-manager
RUN chmod +x /tired-manager

WORKDIR /
RUN apt-get update &&\
    apt-get install -y binutils libproj-dev gdal-bin p7zip-full nco openssh-client
RUN pip install requests numpy shapely matplotlib boto3 python-dotenv netCDF4 pyproj xarray dask bottleneck cartopy fiona
COPY ./main.py /main.py
COPY ./config.py /config.py
COPY ./jobs /jobs
COPY ./lib /lib
USER 1000:1000

# Allow job to run for 35 minutes
# ENTRYPOINT ["python", "main.py"]
ENTRYPOINT ["/tired-manager", "--job-time=2100"]
