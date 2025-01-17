'''
	Sets up file structure, determines date of interest, coordinates downloading and cropping shapefiles, retrospective data,
    and operational data, then creates maps using the data. Lastly, moves the new maps to where they need to be.
  
  usage:
		python main.py <YYYYMMDD>
  
  YYYYMMDD : str : OPTIONAL, date of interest (defaults to today's date if not provided)
  
  Other configuration available in config.py
'''

import datetime
import sys
import os
import shutil
import gzip
from zoneinfo import ZoneInfo

import config

from lib.get_shapefiles import get_shapefiles
from lib.get_nwm_retro import get_nwm_retro
from lib.get_nwm_oper import get_nwm_oper
from lib.create_nwm_nedews_products import create_products
from lib.s3_bucket import send_to_s3
from lib.utils import log_errors

# Ensure that the defined directories exists
def setup(config):
  for dir in [
    config.temp_dir,
    config.retro_data_dir,
    config.oper_data_dir,
    config.output_dir,
    config.us_shp_dir,
    config.nhdplus_dir
  ]:
    if not os.path.exists(dir): os.mkdir(dir)
  
  # Ensure precalculated streamflow_id file is extracted
  streamflow_extracted_file_path = os.path.join(config.writable_dir, 'streamflow_ids.npy')
  if not os.path.exists(streamflow_extracted_file_path):
    streamflow_zip_file_path = os.path.join(config.lib_dir, 'streamflow_ids.npy.gz')
    with gzip.open(streamflow_zip_file_path,"rb") as f_in, open(streamflow_extracted_file_path,"wb") as f_out:
      shutil.copyfileobj(f_in, f_out)

# Determine if user provided a target date or if default should be used
def get_date(args):
  # Strip known irrelevant args out
  dates = [arg for arg in args if arg not in ['python', 'main.py']]

  # Assign date of interest (YYYYMMDD, defaults to current day).
  if len(dates)==1:
    # provided day from command line argument
    YYYYMMDD = args[1] if (type(args[1]) is str) else str(args[1])
  else:
    # current day, accounting for server being in GMT while files/cron trigger being in ExT
    YYYYMMDD = datetime.datetime.now(ZoneInfo('US/Eastern')).strftime('%Y%m%d')

  # Analyses for dates before Mar 15 will only include retro output for 1979.
  if YYYYMMDD[-4:]<'0315' or YYYYMMDD[-4:]>='1230':
    retro_start_year = '1980'
  else:
    retro_start_year = '1979'
      
  return YYYYMMDD, retro_start_year

def main():
  # Ensure proper file structure
  setup(config)

  # Get target date and start year
  YYYYMMDD, retro_start_year = get_date(sys.argv)  

  # Ensure shapefiles are available
  get_shapefiles(config)

  # Get necessary retrospective and operational data
  get_nwm_retro(config, YYYYMMDD, retro_start_year)
  get_nwm_oper(config, YYYYMMDD)

  # Create maps from the new data
  for dataset_type_dict in config.products:
    create_products(config, YYYYMMDD, retro_start_year, dataset_type_dict)
  
  ######################
  # NOTE: if the products were created on a previous run then the code below will not execute!!!
  #    create_products function has a sys.exit() statement to stop execution if the products already exist
  ######################

  # Move new maps to S3 bucket if the correct number of files exist, otherwise clear the
  #   output directory so that the next run can try again
  numExpectedImageProducts = sum([len(config.regions.keys())*len(p['summary_lengths'])*p['varlen'] for p in config.products])
  new_output_dir = os.path.join(config.output_dir, f'{YYYYMMDD}_method1')
  new_dir_len = len(os.listdir(new_output_dir))
  if new_dir_len == numExpectedImageProducts:
    send_to_s3(new_output_dir)
  else:
    shutil.rmtree(new_output_dir)
  
  # Keep three days of output files, delete oldest if there are more
  output_dirs_to_keep = []
  for i in range(3):
    output_dirs_to_keep.append((datetime.datetime.strptime(YYYYMMDD, '%Y%m%d') - datetime.timedelta(days=i)).strftime('%Y%m%d') + '_method1')
  product_dirs = os.listdir(config.output_dir)
  product_dirs.sort()
  for product_dir in product_dirs:
    if product_dir not in output_dirs_to_keep:
      shutil.rmtree(os.path.join(config.output_dir, product_dir))


if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    # Log error to file then propagate it
    log_errors(e, config.writable_dir, 'error_logs.txt')
    raise