"""
Copyright (c) 2024 Erico NETTO

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

You must provide a copy of this license with any distribution of this software.
Any modifications must retain the original developer's name: ERICO NETTO.
Derived works must also be open-source under the same license.
"""



import os
from pathlib import Path
import importlib.util
from flask import Flask, request, jsonify
from inspect import getmembers, isfunction
import inspect
import types


root_folder = os.getenv('PYHON_MODULES_DIRECTORY', 'application_layer')
ignore_str =  os.getenv('IGNORE', 'venv,__pycache__,secrets')
ignore_list = [item.strip() for item in ignore_str.split(',')]
apify_modules_args  = os.getenv('MODULES_ARGS', None)
debug_mode = os.getenv('DEBUG', "false") == "true"
port = int(os.getenv('EXPOSE_PORT', 9000))


print(f"root_folder={root_folder}")
print(f"ignore_str={ignore_str}")
print(f"ignore_list={ignore_list}")
print(f"apify_modules_args={apify_modules_args}")
print(f"debug_mode={debug_mode}")
print(f"port={port}")

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

    root_folder_path = Path(root_folder)
    test_path_resolved = test_path.resolve()

    for parent_path in paths_list:
        parent_path_resolved = Path(os.path.join(root_folder_path, parent_path)).resolve()
        if test_path_resolved.is_relative_to(parent_path_resolved):
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


        if not is_subpath_of_any(file,ignore):
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
                if request.mimetype == 'application/json':
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

        print(f"Importing module {module_path}")
        modules[module_name] = import_module_from_path(str(module_path))


        for function_name, module_func in getmembers(modules[module_name], isfunction):
            #this 'if' is to avoid adding functions from imported modules inside the main module 'module_name' that we are geting functions from
            file_module_where_function_where_declared = module_func.__code__.co_filename
            module_where_function_where_declared = os.path.splitext(os.path.basename(file_module_where_function_where_declared))[0]
            if module_where_function_where_declared == module_name:

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
                    if not param in ["apify_app", "apify_request"]:
                        endpoint_description["body"][param] = "value"


            if module_func.__doc__:
                endpoint_description["doc"] = module_func.__doc__


            routes.append(endpoint_description)

    # Return the routes as a JSON object or render it in HTML if desired
    return jsonify({"routes": routes})


print("Initializing")
initialize()
absolute_root_path = str(Path(root_folder).absolute())
os.chdir(absolute_root_path)
# Run the app
if __name__ == "__main__":
    apify_app.run(host='0.0.0.0', debug=debug_mode, use_reloader=False, port=port)
