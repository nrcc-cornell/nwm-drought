# NWM drought indices for the Northeast U.S.

## About this project
National Water Model v3.0 soil moisture and streamflow output are used to assess drought conditions in the northeastern United States. NWM operational model output provides current conditions, while NWM retrospective simulation output (1979-2020) provides climatological context. The drought indices are calculated using the percentile of current conditions (soil moisture or streamflow) relative to historical conditions during the available NWM retrospective period. Drought index bins and color-coding follow those used by the National Drought Mitigation Center.

Maps of these indices are available at: https://nedews.nrcc.cornell.edu/ .

Updated to Python 3 and transferred to a Fly.io/Cloudflare R2/AWS S3 pattern July 2024 by BE99.

## Execution
main.py: 6 9-21/2 * * *
  main.py coordinates getting shapefiles, retrospective, and operational data, then creating product maps, and finally moving maps to production
  It skips any section that has successfully completed, so executing several times ina day is not a problem.

## 1. Docker Image
This project utilizes Docker, make sure you have it installed or convert the code to use a Conda env that has the dependencies listed in the Dockerfile (will require some additional configuration to run this way).

In order to run the code locally, open `Dockerfile` and replace `ENTRYPOINT ["/tired-manager", "--job-time=2100"]` with `ENTRYPOINT ["python", "main.py"]`.

Then build the Docker image:
```shell
$ docker build -t nwm_drought:1 -f Dockerfile .
```

And execute the code:
```shell
$ docker-compose run --rm nwm_drought python main.py
```

## 2. Required shapefiles

All required shapefiles are downloaded and subset in `lib/get_shapefiles.py`:

Two directories within `nwm_drought_volume` are created and populated with static shapefiles:

'us_shapefile' : for political boundaries

'NHDPlus' : regional stream reach information

NOTE: the 'NHDPlus' download is very large (~10GB) and takes a while to download.


## 3. NWM data management
#### Retrospective simulations
Retrospective simulation output is downloaded, filtered for variables and region of interest, and saved for a window of dates each year in `lib/get_nwm_retro.py`.

A 'nwm_retro_data' directory is created in `nwm_drought_volume`, containing the saved files. Due the size of these files, only a running window relative to the current date is retained. This script is executed each day to refresh the rolling window of files (about 1 month of data for each available year by default to accommodate 1, 7, 14, and 28-day lookbacks).

#### Operational model analyses
Operational model output is also downloaded, filtered and saved each day in `lib/get-nwm-oper.py`.

A 'nwm_oper_data' directory is created in `nwm_drought_volume`, containing the saved files. Unlike the retrospective simulation output, the operational model output is only retained at the data source for two days. Since there is not an easily accessible archive of operational model output, we copy the filtered files into an R2 bucket in case we need them later. Locally, about 1 month of files are retained for lookbacks. Note that it may take a few weeks to accumulate the necessary period of files, as they become available, to perform calculations.


## 4. NWM drought index maps
With all of the necessary NWM output data in place, create the drought index products for current soil moisture at various depths (0-10, 10-40, 40-100, 100-200cm) and streamflow conditions with various lookbacks (1, 7, 14, 28-day). This occurs in `lib/create_nwm_nedews_products.py`.

A 'nwm_drought_indicator_output' directory is created in `nwm_drought_volume`, containing additional directories tagged with YYYYMMDD date format. Inside the date directories, map images for multiple regions are saved. The date that the run is specified for is the date directory that is pushed to the live S3 bucket at the end of the script.

These live maps are visible at:
https://nedews.nrcc.cornell.edu/
