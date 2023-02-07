import tarfile
import paramiko
import json
import importlib
import logging
import os
from fabric.api import env, run, put, cd, task
import mysql.connector

# Configurer le logger
logging.basicConfig(filename="deploy.log", level=logging.ERROR )

# Charger les variables depuis le fichier de configuration
with open('config.json') as f:
    config = json.load(f)

def task(name, callback):
    print(f"Executing task {name}")
    try:
        callback()
        logging.info(f"Task {name} completed")
        print(f" ==> Task {name} completed")
    except Exception as e:
        logging.error(f"Error while executing task {name}: {e}")

def deploy(hostname, username, password):
    # Créer une nouvelle instance de la classe SSHClient
    client = paramiko.SSHClient()

    # Autoriser les connexions SSH à des hôtes non connus
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    # Se connecter à l'hôte distant
    try:
        client.connect(hostname=hostname, username=username, password=password)
    except Exception as e:
        logging.error(f"Error while connecting to host {hostname}: {e}")
        return
    
    # Ouvrir un canal SFTP
    sftp = client.open_sftp()
    
    # Compression du dossier local 
    with tarfile.open(config['local_folder']+'.tar', "w") as tar:
        task("Compression du dossier local", lambda : tar.add(config['local_folder'], arcname=os.path.basename(config['local_folder'])))

    
    # Récupération de la version courante sur l'hôte distant
    try:
        stdin, stdout, stderr = client.exec_command("cat {}/version.txt".format(config['remote_folder']))
        current_version = stdout.read().strip()
    except Exception as e:
        logging.error(f"Error while getting current version on host {hostname}: {e}")
        return
    
    # Création d'un nouveau dossier de version
    new_version_folder = "{}/v{}".format(config['remote_folder'], config['new_version'])
    task("Création d'un nouveau dossier de version", lambda : client.exec_command("mkdir {}".format(new_version_folder)))
    
    # Téléversement du fichier tar
    task("Téléversement du fichier tar", lambda: sftp.put(config['local_folder']+'.tar', new_version_folder+'.tar'))
    
    # Décompression du fichier tar sur le nouveau dossier de version
    task("Décompression du fichier tar sur le nouveau dossier de version", lambda:  client.exec_command('tar -xf {} -C {}'.format(new_version_folder+'.tar', new_version_folder)))
     
    # Création d'un lien symbolique vers le dossier partagé
    task("Création d'un lien symbolique vers le dossier partagé", lambda :  client.exec_command("ln -sfn {} {}/shared".format(config['remote_folder']+"/shared", new_version_folder)))
    
    # Mise à jour de la version courante
    task("Mise à jour de la version courante", lambda : client.exec_command("echo {} > {}/version.txt".format(config['new_version'], config['remote_folder'])))

    # Création d'un lien symbolique vers le dossier courant
    task("Création d'un lien symbolique current", lambda :  client.exec_command("ln -sfn {} {}/current".format(new_version_folder, config['remote_folder'])))

    #Suppression du tar distant
    task("Suppression du fichier tar distant", lambda: sftp.remove(new_version_folder+'.tar'))

    # Executer la fonction after si configurée
    if 'after_transfer_function' in config:
        task("Exécution de la fonction après transfert", lambda: importlib.import_module(config['after_transfer_function']).after(client,config))

    # Fermer la connexion
    client.close()

def backup_database(config):
    # Get current date and time
    now = datetime.datetime.now()
    filename = "backup_{}.sql".format(now.strftime("%Y-%m-%d_%H-%M-%S"))
    remote_folder = "~/backup"
    # Create backup command
    cmd = "mysqldump -u {} -p{} {} > {}".format(config["db_user"], config["db_password"], config["db_name"], filename)

    # Execute backup command
    run(cmd)

    # Transfer backup file to remote folder
    put(filename, remote_folder)

    # Remove local backup file
    os.remove(filename)

    # Return backup filename
    return filename

def update_database(config):
    # Connect to database
    conn = mysql.connector.connect(
        host=config["db_host"],
        user=config["db_user"],
        password=config["db_password"],
        database=config["db_name"]
    )

    # Create cursor
    cursor = conn.cursor()

    # Read SQL file
    with open("update_database.sql", "r") as f:
        sql = f.read()

    # Execute SQL commands
    cursor.execute(sql)

    # Commit changes
    conn.commit()

    # Close cursor and connection
    cursor.close()
    conn.close()

for host in config['hosts']:
	deploy(host['hostname'], host['username'], host['password'])
    