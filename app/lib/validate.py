# SPDX-FileCopyrightText: 2021-2022 Citadel and contributors
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import yaml
from jsonschema import validate
import yaml
import traceback

scriptDir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
nodeRoot = os.path.join(scriptDir, "..")

with open(os.path.join(nodeRoot, "db", "dependencies.yml"), "r") as file: 
  dependencies = yaml.safe_load(file)

# Validates app data
# Returns true if valid, false otherwise
def validateApp(app: dict):
    if 'version' in app and str(app['version']) == "3":
        # The app-cli does this validation now
        return True
    elif 'citadel_version' not in app:
        print("Unsupported app version")
        return False
    else:
        return True

# Read in an app.yml file and pass it to the validation function
# Returns true if valid, false otherwise
def validateAppFile(file: str):
    with open(file, 'r') as f:
        return validateApp(yaml.safe_load(f))

# Returns all dirs in the dir
def findApps(dir: str):
    apps = []
    # Only get directories in the dir, but not recursively
    for root, dirs, files in os.walk(dir, topdown=False):
        for name in dirs:
            app_dir = os.path.join(root, name)
            if os.path.isfile(os.path.join(app_dir, "app.yml")) or os.path.isfile(os.path.join(app_dir, "docker-compose.yml")):
                apps.append(name)
    return apps


# Lists all folders in a directory and checks if they are valid
# A folder is valid if it contains an app.yml file
# A folder is invalid if it doesn't contain an app.yml file
def findAndValidateApps(dir: str):
    apps = []
    app_data = {}
    for subdir in os.scandir(dir):
        if not subdir.is_dir():
            continue
        app_dir = subdir.path
        if os.path.isfile(os.path.join(app_dir, "app.yml.jinja")):
            os.chown(app_dir, 1000, 1000)
            os.system("docker run --rm -v {}:/apps -u 1000:1000 {} /app-cli preprocess --app-name '{}' /apps/{}/app.yml.jinja /apps/{}/app.yml --services 'lnd'".format(dir, dependencies['app-cli'], subdir.name, subdir.name, subdir.name))
        if os.path.isfile(os.path.join(app_dir, "app.yml")):
            apps.append(subdir.name)
            # Read the app.yml and append it to app_data
            with open(os.path.join(app_dir, "app.yml"), 'r') as f:
                app_data[subdir.name] = yaml.safe_load(f)
        else:
            print("App {} has no app.yml".format(subdir.name))
    # Now validate all the apps using the validateAppFile function by passing the app.yml as an argument to it, if an app is invalid, remove it from the list
    for app in apps:
        appyml = app_data[app]
        if not validateApp(appyml):
            apps.remove(app)
            print("Warning: App {} is invalid".format(app))
            # Skip to the next iteration of the loop
            continue
        # More security validation
        should_continue=True
        if 'dependencies' in appyml['metadata']:
            for dependency in appyml['metadata']['dependencies']:
                if isinstance(dependency, str):
                    if dependency not in apps and dependency not in ["bitcoind", "lnd", "electrum"]:
                        print("WARNING: App '{}' has unknown dependency '{}'".format(app, dependency))
                        apps.remove(app)
                        should_continue=False
                    if dependency == app:
                        print("WARNING: App '{}' depends on itself".format(app))
                        apps.remove(app)
                        should_continue=False
                else:
                    for subDependency in dependency:
                        if subDependency not in apps and subDependency not in ["bitcoind", "lnd", "electrum", "c-lightning"]:
                            print("WARNING: App '{}' has unknown dependency '{}'".format(app, subDependency))
                            apps.remove(app)
                            should_continue=False
                        if subDependency == app:
                            print("WARNING: App '{}' depends on itself".format(app))
                            apps.remove(app)
                            should_continue=False
        if not should_continue:
            continue
        if 'containers' in appyml:
            for container in appyml['containers']:
                if 'permissions' in container:
                    for permission in container['permissions']:
                        if permission not in appyml['metadata']['dependencies'] and permission not in ["root", "hw"]:
                            print("WARNING: App {}'s container '{}' requires the '{}' permission, but the app doesn't list it in it's dependencies".format(app, container['name'], permission))
                            apps.remove(app)
                            # Skip to the next iteration of the loop
                            continue
    return apps
