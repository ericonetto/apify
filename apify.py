"""
This script was developpd by ERICO NETTO
First version on 20-sep-2024

This script when executed will automatically generate API endpoints for Python functions existing in Python modules in a specified directory.
This script will use the following parameters:

ignore = ["venv", "__pycache__"]
root_directory = "."

In the 'root_directory' it will go through all folders and subfolders for Python scripts, ignoring folders listed in 'ignore'
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

"""



import os
from pathlib import Path
import importlib.util
from flask import Flask, request, jsonify
from inspect import getmembers, isfunction
import inspect
import types





ignore = ["venv", "__pycache__"]
root_directory = "."





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


def find_py_files_with_pathlib(directory, ignore =[]):
    root_directory_path = Path(directory)
    ignore_paths =[]
    for p in ignore:
        ignore_paths.append(Path(p).relative_to(root_directory_path))

    file_list = []
    for file in root_directory_path.rglob("*.py"):

        file_file = file.relative_to(root_directory_path)


        if not is_subpath_of_any(file_file,ignore_paths):
            file_list.append(str(file_file))

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


app = Flask(__name__)


python_files = find_py_files_with_pathlib(root_directory, [os.path.basename(__file__)] + ignore)
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
    app.route(route_path, methods = methods)(new_func)

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
        response = app.response_class()
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Length'] = len(str({"data":result}))
        return response


    return {"data":result}, 200


##########################################

##########################################
def initialize():
    for module_path in python_files:

        module_name = module_path[:-3]

        modules[module_name] = import_module_from_path(module_path)


        for function_name, module_func in getmembers(modules[module_name], isfunction):

            route_path = "/" +  module_name + "/" + function_name

            function_name = route_path.replace("/", "_")

            dynamic_route_creator(receive_data, route_path, function_name, ['POST', 'GET'])


@app.route("/")
def documentation():
    """
    This endpoint provides documentation for all the available routes.
    """
    # Get all the routes from the app
    routes = []
    for rule in app.url_map.iter_rules():
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
                    endpoint_description["body"][param] = "value"
            if module_func.__doc__:
                endpoint_description["doc"] = module_func.__doc__


        routes.append(endpoint_description)

    # Return the routes as a JSON object or render it in HTML if desired
    return jsonify({"routes": routes})


if __name__ == '__main__':
    initialize()
    # Run the app on port 9000
    app.run(debug=True, port=9000)

