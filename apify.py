"""
This script was developpd by ERICO NETTO
First version on 20-sep-2024

This script when executed will automatically generate API endpoints for Python functions existing in Python modules in a specified folder.
This script will use the following parameters:

ignore = ["venv", "__pycache__"]
root_folder = "."

In the 'root_folder' it will go through all folders and subfolders for Python scripts, ignoring folders listed in 'ignore'
For each Python module found, the script will generate API endpoints for each of the Python functions existing within the module
The API endpoints will have the same path as the path of the Python file found plus the name of the Python module found plus the name of the function, example:

<server url>/folder1/folder2/module_name/function_name

To view the DOCUMENTATION of all created endpoints, simply do a GET in the root folder: <server url>/

The generated endpoints will work in the same way as the functions they are based on, if the function does not receive any parameters, 
both the GET and POST methods will return what the function returns. 
The return will always be in the form: {"data": <data returned by the function>}
If the function does not return any value, the return will be: {"data": null}

The function parameters must be passed in JSON format via POST
For example, if the function is:
def sum(a, b)
Then in the POST the body must be, for example {"a": 1, "b":2 }

There are two parameters internal to this module that will be automatically passed to any functions if the function have one or both of these parameters 'apify_app' and 'apify_request'
'apify_app' is the apify_app object of this module, defined in the line: apify_app = Flask(__name__)
'apify_request' is the request object that is passed when the flask endpoint function is called
'apify_modules_args' arguments to be used in the python scripts. In case you need to pass os.getenv args they will be obteined here and then could be used in the modules if in the function parameter 

Usages examples:
def example_to_redirect(apify_app):
    redirect_url = "https://url.to.redirect.com/path"
    return apify_app.redirect(redirect_url)

def exmaple_to_get_query_string(apify_request):
    query_string = apify_request.query_string
    return f'Query string: {query_string}'


def exmaple_get_a_enviroment_variable(apify_modules_args):
    return f'My enviroment variable is : {apify_modules_args}'


Env varibles that could be passed to this stript
PYHON_MODULES_FOLDER -> this is where is the root folder where are the pyhton modules where the funtions will be transformed in API endpoints
IGNORE -> this what folders to ignore that are sub folders inside of the PYHON_MODULES_FOLDER
MODULES_ARGS -> this argument will be passed to any funtion that has 'apify_modules_args' as input argument
"""



import os
from pathlib import Path
import importlib.util
from flask import Flask, request, jsonify
from inspect import getmembers, isfunction
import inspect
import types



root_folder = os.getenv('PYHON_MODULES_DIRECTORY', 'archives')

ignore_str =  os.getenv('IGNORE', 'venv,__pycache__')
ignore_list = [item.strip() for item in ignore_str.split(',')]

apify_modules_args  = os.getenv('MODULES_ARGS', None)


# DO NOT EDIT BELOW THIS LINE 
#############################
def is_subpath_of_any(test_path: Path, paths_list: list[Path]) -> bool:
    """
    Check if 'test_path' is a subpath of any path in 'paths_list'.
    
    Args:
        test_path (Path): The path to test.
        paths_list (list[Path]): A list of paths to compare against.

    Returns:
        bool: True if 'test_path' is a subpath of any path in 'paths_list', False otherwise.
    """
    test_path_resolved = test_path.resolve()

    for parent_path in paths_list:
        if test_path_resolved.is_relative_to(parent_path.resolve()):
            return True
    
    return False


def find_py_files_with_pathlib(folder, ignore =[]):
    root_folder_path = Path(folder)
    ignore_paths =[]
    for p in ignore:
        ignore_path = Path(os.path.join(folder, p))
        ignore_paths.append(ignore_path.relative_to(root_folder_path))

    file_list = []
    for file in root_folder_path.rglob("*.py"):

        file_file = file.relative_to(root_folder_path)


        if not is_subpath_of_any(file_file,ignore_paths):
            file_list.append(file)

    return file_list

# Function to dynamically import a module given its full path
def import_module_from_path(path):
    # Create a module spec from the given path
    spec = importlib.util.spec_from_file_location("module_name", path)

    # Load the module from the created spec
    module = importlib.util.module_from_spec(spec)

    # Execute the module to make its attributes accessible
    spec.loader.exec_module(module)

    # Return the imported module
    return module


apify_app = Flask(__name__)


python_files_paths = find_py_files_with_pathlib(root_folder, [os.path.basename(__file__)] + ignore_list)
modules = {}

# Function to create a new function with a dynamic name and decorator
def dynamic_route_creator(original_func, route_path, new_name, methods=['POST']):
    
    # Create a new function with the dynamic name
    new_func = types.FunctionType(
        original_func.__code__,
        original_func.__globals__,
        new_name,
        original_func.__defaults__,
        original_func.__closure__
    )
    
    # Manually add the route for the new function
    apify_app.route(route_path, methods = methods)(new_func)

    return new_func

def receive_data():
    data = None
    result = None

    end_point_path = request.path
    module_name = "/".join(end_point_path.split("/")[:-1])[1:]
    function_name = end_point_path.split("/")[-1]

    if module_name in modules:

        module_func = getattr(modules[module_name], function_name, None)

        func_signature = inspect.signature(module_func)

        list_parameters = list(func_signature.parameters)

        if len(list_parameters)>0:
            if request.method == "POST" or request.method == 'HEAD':
                try:
                    data = request.get_json()
                    # Print the received data
                    print("\n\n")
                    print(f"Received data: {data}")

                except Exception as e:
                    return str(e), 500

        if "apify_app" in list_parameters:
            if data==None:
                data = {}
            data["apify_app"] = apify_app

        if "apify_request" in list_parameters:
            if data==None:
                data = {}
            data["apify_request"] = request

        if "apify_modules_args" in list_parameters:
            if data==None:
                data = {}
            data["apify_modules_args"] = apify_modules_args

        kwargs = data

        if kwargs:
            try:
                result = module_func(**kwargs)
            except Exception as e:
                return str(e), 500
        else:
            try:
                result = module_func()
            except Exception as e:
                return str(e), 500


    if request.method == 'HEAD':
        # Respond with headers but no body
        response = apify_app.response_class()
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Length'] = len(str({"data":result}))
        return response

    if isinstance(result, int) or isinstance(result, float) or isinstance(result, dict) or isinstance(result, list) or isinstance(result, bool) or isinstance(result, str) or result==None:
        return {"data":result}, 200
    else:
        return result


##########################################

##########################################
def initialize():
    for module_path in python_files_paths:

        module_name = module_path.stem

        modules[module_name] = import_module_from_path(str(module_path))


        for function_name, module_func in getmembers(modules[module_name], isfunction):


            route_path = str(Path(root_folder)).replace(str(module_path.parent),"/")

            route_path = route_path +  module_name + "/" + function_name

            function_name = route_path.replace("/", "_")

            dynamic_route_creator(receive_data, route_path, function_name, ['POST', 'GET'])


@apify_app.route("/")
def documentation():
    """
    This endpoint provides documentation for all the available routes.
    """
    # Get all the routes from the app
    routes = []
    for rule in apify_app.url_map.iter_rules():
        # Skip endpoint if it has no methods or is an internal rule
        endpoint_description={
            "endpoint": rule.rule,
            "methods": list(rule.methods)
            
        }

        module_name = "/".join(rule.rule.split("/")[:-1])[1:]
        function_name = rule.rule.split("/")[-1]

        if module_name in modules:

            module_func = getattr(modules[module_name], function_name, None)

            func_signature = inspect.signature(module_func)

            list_parameters = list(func_signature.parameters)
            if len(list_parameters)>0:
                endpoint_description["body"]={}
                for param in list_parameters:
                    if param != "apify_app":
                        endpoint_description["body"][param] = "value"
                    if param != "apify_request":
                        endpoint_description["body"][param] = "value"


            if module_func.__doc__:
                endpoint_description["doc"] = module_func.__doc__


        routes.append(endpoint_description)

    # Return the routes as a JSON object or render it in HTML if desired
    return jsonify({"routes": routes})


if __name__ == '__main__':
    initialize()
    absolute_root_path = str(Path(root_folder).absolute())
    os.chdir(absolute_root_path)
    # Run the app on port 9000
    apify_app.run(debug=True, use_reloader=False, port=9000)

