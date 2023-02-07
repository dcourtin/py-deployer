# deployer_hooks.py
def after(client, config):
    sftp = client.open_sftp()
    versions = ('v1.1','v1.2','v1.3','v1.4')
    for version in versions:
        versionPath=config['remote_folder']+'/'+version
        print(versionPath)
        sftp.rmdir(versionPath)
            