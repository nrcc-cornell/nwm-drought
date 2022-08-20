# NWM drought indices for the Northeast U.S.

## About this project
National Water Model v2.1 soil moisture and streamflow output are used to assess drought conditions in the northeastern United States. NWM operational model output provides current conditions, while NWM retrospective simulation output (1979-2020) provides climatological context. The drought indices are calculated using the percentile of current conditions (soil moisture or streamflow) relative to historical conditions during the available NWM retrospective period. Drought index bins and color-coding follow those used by the National Drought Mitigation Center.

Maps of these indices are available at: https://nedews.nrcc.cornell.edu/ .

## 1. Python environment
Scripts in this project require a Python 2 environment with necessary dependencies. A conda yml file is provided (conda_env/nwm-drought.yml). To install this environment on Mac/Linux:

```shell
$ conda env create -f nwm-drought.yml
```

Once created, activate your new environment:

```shell
$ conda activate nwm-drought
```

## 2. Required shapefiles

All required shapefiles are downloaded/created by running the following script:

```shell
$ python get-shapefiles.py
```

Three top-level directories are created and populated with static shapefiles:

'us_shapefile', 'world_shapefile' : for political boundaries

'NHDPlus' : regional stream reach information

## 3. NWM data management
#### Retrospective simulations
Retrospective simulation output is downloaded, filtered for variables and region of interest, and saved for a window of dates each year using:

```shell
$ python get-nwm-retro.py
```

A top-level 'nwm_retro_data' directory is created, containing the saved files. Due the size of these files, only a running window relative to the current date is retained. This script is executed each day to refresh the rolling window of files (about 1 month of data for each available year by default to accommodate 1, 7, 14, and 28-day lookbacks).

#### Operational model analyses
Operational model output is also downloaded, filtered and saved each day using:

```shell
$ python get-nwm-oper.py
```

A top-level 'nwm_oper_data' directory is created, containing the saved files. Unlike the retrospective simulation output, the operational model output is only retained at the data source for two days. Since there is not an easily accessible archive of operational model output, we choose to not rotate off these saved files beyond the period needed. Note that it may take a few weeks to accumulate the necessary period of files, as they become available, to perform calculations.

## 4. NWM drought index maps
With all of the necessary NWM output data in place, create the drought index products.

For current soil moisture at various depths (0-10, 10-40, 40-100, 100-200cm):
```shell
$ python create-nwm-nedews-products.py SOIL_M
```

For streamflow conditions with various lookbacks (1, 7, 14, 28-day):
```shell
$ python create-nwm-nedews-products.py streamflow
```

A top-level 'nwm_drought_indicator_output' directory is created, containing additional directories tagged with YYYYMMDD date format. Inside the date directories, map images for multiple regions are saved.

An additional 'current' directory inside 'nwm_drought_indicator_output' holds the most recent maps created.

## 5. NE DEWS products
The 'current' maps are moved into production via:

```shell
$ aws s3 sync nwm_drought_indicator_output/current_method1/ s3://nedews.nrcc.cornell.edu/NWM_maps/
```

These live maps are visible at:
https://nedews.nrcc.cornell.edu/
