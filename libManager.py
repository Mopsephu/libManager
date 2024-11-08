import subprocess
import os
import re

class libManager:
    """
    A class to manage Python libraries for a project, allowing for automatic installation,
    details retrieval, dependency resolution, and requirements file creation.
    """

    # Set of target libraries for installation/removal.
    libraries_needed: set[str] = None

    # Cached global variables for installed libraries and library details.
    _installed_libs_: set[str] = None
    _lib_details_: dict = {}

    def get_installed_libs(self, update: bool = False) -> set[str]:
        """
        Returns a set of currently installed libraries.

        Args:
            update (bool): If True, refresh the cache of installed libraries.

        Returns:
            set[str]: A set of installed library names.
        """
        if self._installed_libs_ is None or update:
            output = subprocess.check_output(['pip', 'list']).decode('utf-8').splitlines()
            self._installed_libs_ = {line.split()[0] for line in output[2:]}
        return self._installed_libs_

    def get_lib_details(self, lib: str) -> dict:
        """
        Retrieves details of a specified library, including dependencies and usage by other libraries.

        Args:
            lib (str): The name of the library to retrieve details for.

        Returns:
            dict: Library details with keys:
                                        'version',
                                        'summary',
                                        'home-page',
                                        'author',
                                        'author-email',
                                        'license',
                                        'location',
                                        'requires',
                                        'required_by'.
        """
        if lib not in self._lib_details_:
            if lib in self.get_installed_libs():
                output = subprocess.check_output(['pip', 'show', lib]).decode('utf-8')
                VersText: int = output.find("Version: ")+9
                SumText: int = output.find("Summary: ", VersText)+9
                HmPgText: int = output.find("Home-page: ", SumText)+11
                AuthText: int = output.find("Author: ", HmPgText)+8
                AuthMailText: int = output.find("Author-email: ", AuthText)+14
                LicText: int = output.find("License: ", AuthMailText)+9
                LocText: int = output.find("Location: ", LicText)+10
                ReqText: int = output.find("Requires: ", LocText)+10
                ReqByText: int = output.find("Required-by: ", ReqText)+13

                #Индексация идёт так: [a, b)
                requires = output[ReqText : ReqByText - 13].strip().split(", ")
                required_by = output[ReqByText : ].strip().split(", ")
                self._lib_details_[lib] = {
                    'version': output[VersText : SumText-9].strip(),
                    'summary': output[SumText : HmPgText-11].strip(),
                    'home-page': output[HmPgText : AuthText-8].strip(),
                    'author': output[AuthText : AuthMailText-14].strip(),
                    'author-email': output[AuthMailText : LicText-9].strip(),
                    'license': output[LicText : LocText-10].strip(),
                    'location': output[LocText : ReqText-10].strip(),
                    'requires': set(requires) if requires != [''] else set(),
                    'required_by': set(required_by) if required_by != [''] else set()
                }
            else:
                self._lib_details_[lib] = {'required_by': set(), 'requires': set()}
        return self._lib_details_[lib]

    def get_all_dependencies(self, lib: str) -> set[str]:
        """
        Recursively retrieves all dependencies of a specified library.

        Args:
            lib (str): The library to retrieve dependencies for.

        Returns:
            set[str]: A set of all dependencies for the library.
        """
        dependencies = set()
        stack = [lib]
        while stack:
            current_lib = stack.pop()
            if current_lib not in dependencies:
                dependencies.add(current_lib)
                stack.extend(self.get_lib_details(current_lib)['requires'] - dependencies)
        dependencies.discard(lib)
        return dependencies

    def create_actual_requirements(self, path_to_py: str = None, additional_libs: set[str] = None) -> None:
        """
        Creates a minimal requirements.txt file based on the specified .py file's imports
        and additional libraries.

        Args:
            path_to_py (str): Path to the .py file for scanning imports.
            additional_libs (set[str]): Additional libraries to include in requirements.
        """
        stated_libs: set = set()
        if path_to_py:
            if os.path.isfile(path_to_py) and path_to_py.lower().endswith("py"):
                with open(path_to_py, 'r', encoding='utf-8') as file:
                    pattern = re.compile(r'\w++')
                    for line in file:
                        cur_line: str = line.strip()
                        if cur_line.startswith("from "):
                            stated_libs.add(pattern.search(cur_line[5:]).group())
                        elif cur_line.startswith("import "):
                            stated_libs.add(pattern.search(cur_line[7:]).group())
            else:
                print(f"Specify a file with .py extension!\nCheck the path: {path_to_py}")
        if additional_libs:
            stated_libs.update(additional_libs)
        self.get_installed_libs()
        actual_libs: set = set(stated_libs)
        
        for lib in stated_libs:
            if not lib in self._installed_libs_:
                actual_libs.remove(lib)
        
        if len(actual_libs) > 0:
            special_char: str = '\\' if '\\' in path_to_py else '/'
            with open(os.path.dirname(path_to_py)+f"{special_char}requirements.txt", 'w', encoding='utf-8') as file:
                for lib in actual_libs:
                    version = self.get_lib_details(lib)["version"]
                    file.write(f"{lib}=={version}\n")
        elif path_to_py:
            print(f"No external libraries were found in {os.path.split(path_to_py)[1]}! Please double-check.")

    def init_libs(self):
        """
        Installs the libraries in the libraries_needed set if they are not already installed.
        """
        if self.libraries_needed != set():
            missing_libs = [lib for lib in self.libraries_needed if lib not in self.get_installed_libs()]
            if missing_libs:
                subprocess.call(['pip', 'install', *missing_libs])
                print("All required libraries have been installed!")
            else:
                print("All required libraries are already installed!")

    def deinit_libs(self, can_delete_pip: bool = False):
        """
        Uninstalls the libraries in the libraries_needed set and all their dependencies if not used by other libraries.

        Args:
            can_delete_pip (bool): Allows pip to be deleted if True; otherwise, it is preserved.
        """
        dependencies = set()
        for lib in self.libraries_needed:
            dependencies.add(lib)
            dependencies.update(self.get_all_dependencies(lib))
        
        unused_libs = self.get_installed_libs() - dependencies
        libs_to_delete = {lib for lib in dependencies if not any(dep in unused_libs for dep in self.get_lib_details(lib)['required_by'])}
        survived_libs = dependencies - libs_to_delete

        for lib in survived_libs:
            libs_to_delete -= self.get_lib_details(lib)['requires']
        
        for lib in libs_to_delete:
            if can_delete_pip or lib != "pip":
                subprocess.call(['pip', 'uninstall', lib, '-y'])
            else:
                print(f"Module {lib} will not be automatically removed!\nTo remove it, delete manually or set can_delete_pip to True.")
        print("All dependent libraries have been successfully removed!")

    def __init__(self, target_libs: set = set(), init_at_start: bool = True) -> None:
        """
        Initializes the LibManager with a set of target libraries.

        Args:
            target_libs (set): Libraries to manage.
            init_at_start (bool): If True, automatically installs missing libraries.
        """
        self.libraries_needed = target_libs
        if init_at_start:
            self.init_libs()