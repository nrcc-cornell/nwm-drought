import os
import boto3

class R2Bucket:
  def __init__(self, bucket_name, cf_id, aws_id, aws_secret):
    r2 = boto3.resource(
      's3',
      endpoint_url = f'https://{cf_id}.r2.cloudflarestorage.com',
      aws_access_key_id=aws_id,
      aws_secret_access_key=aws_secret
    )
    self.bucket = r2.Bucket(bucket_name)
  
  def __sync_bucket_directories(self, local_dir_path, local_dirs, web_dirs, verbose=False):
    # if directory in bucket is also in local, remove from list to copy
    # if directory in bucket is not in local and is not in ignore list then it is not needed, delete all files in it
    ignore_dirs = ['pre']
    for web_dir in web_dirs:
      if web_dir in ignore_dirs:
        continue
      elif web_dir in local_dirs:
        if verbose: print('have:', web_dir)
        local_dirs.remove(web_dir)
      else:
        if verbose: print('delete:', web_dir)
        self.bucket.objects.filter(Prefix=web_dir).delete()
    
    # for each needed directory copy it's contents into the bucket
    for local_dir in local_dirs:
      if verbose: print('need:', local_dir)
      dir_path = os.path.join(local_dir_path, local_dir)
      for f_name in os.listdir(dir_path):
        if verbose: print(f'   copying:', f_name)
        self.bucket.upload_file(os.path.join(dir_path, f_name), f'{local_dir}/{f_name}')

  def __sync_bucket_files(self, local_dir_path, local_files, web_files, verbose=False):
    # remove all unneeded files from bucket
    to_delete = []
    for web_file in web_files:
      if web_file not in local_files:
        if verbose: print('delete:', web_file)
        to_delete.append({'Key': web_file})
    if len(to_delete):
      self.bucket.delete_objects(Delete={'Objects': to_delete})
    
    # push all local files to the bucket, overwriting if necessary
    for local_file in local_files:
      if verbose: print('copying:', local_file)
      self.bucket.upload_file(os.path.join(local_dir_path, local_file), local_file)
  
  def __separate_directories_from_files(self, dir_contents):
    files = []
    dirs = []
    for name in dir_contents:
      name_parts = name.split('/')
      if len(name_parts) == 1 and '.' in name_parts[0]:
        files.append(name)
      elif name_parts[0] not in dirs:
        dirs.append(name_parts[0])
    return files, dirs


  def sync_bucket(self, local_dir_path, verbose=False):
    local_contents = os.listdir(local_dir_path)
    local_files, local_dirs = self.__separate_directories_from_files(local_contents)

    web_contents = [obj.key for obj in self.bucket.objects.all()]
    web_files, web_dirs = self.__separate_directories_from_files(web_contents)

    self.__sync_bucket_directories(local_dir_path, local_dirs, web_dirs, verbose)
    self.__sync_bucket_files(local_dir_path, local_files, web_files, verbose)