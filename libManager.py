import subprocess

class libManager:
    # Множество целевых библиотек (для установки/удаления)
    libraries_needed: set[str] = None

    # Глобальные переменные для кеширования библиотек
    _installed_libs_: set[str] = None
    _lib_details_: dict = {}

    # Возвращает множество установленных библиотек.
    def get_installed_libs(self, update: bool = False)->set[str]:
        if self._installed_libs_ is None or update:
            output = subprocess.check_output(['pip', 'list']).decode('utf-8').splitlines()
            self._installed_libs_ = {line.split()[0] for line in output[2:]}
        return self._installed_libs_

    # Возвращает подробности указанной библиотеки: зависимости, а также в каких библиотеках ещё используется
    def get_lib_details(self, lib: str)->dict:
        if lib not in self._lib_details_:
            if lib in self.get_installed_libs():
                output = subprocess.check_output(['pip', 'show', lib]).decode('utf-8')
                required_by = output[output.rfind("Required-by:") + 13:].strip().split(", ")
                requires = output[output.rfind("Requires: ") + 10:output.rfind("Required-by:") - 2].split(", ")
                self._lib_details_[lib] = {
                    'required_by': set(required_by) if required_by != [''] else set(),
                    'requires': set(requires) if requires != [''] else set()
                }
            else:
                self._lib_details_[lib] = {'required_by': set(), 'requires': set()}
        return self._lib_details_[lib]

    # Возвращает все зависимости указанной библиотеки вплоть до самостоятельных библиотек
    def get_all_dependencies(self, lib):
        dependencies = set()
        stack = [lib]
        while stack:
            current_lib = stack.pop()
            if current_lib not in dependencies:
                dependencies.add(current_lib)
                stack.extend(self.get_lib_details(current_lib)['requires'] - dependencies)
        dependencies.discard(lib)
        return dependencies

    # Устанавливает библиотеки из множества libraries_needed
    def init_libs(self):
        missing_libs = [lib for lib in self.libraries_needed if lib not in self.get_installed_libs()]
        if missing_libs:
            subprocess.call(['pip', 'install', *missing_libs])
            print("Все необходимые библиотеки были установлены!")
        else:
            print("Все необходимые библиотеки уже установлены!")

    # Удаляет библиотеки из множества libraries_needed, а также все их зависимости, если они не используются в совершеннно сторонних библиотеках
    def deinit_libs(self, can_delete_pip: bool = False):
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
            if can_delete_pip or lib != "pip": subprocess.call(['pip', 'uninstall', lib, '-y'])
            else: print(f"Модуль {lib} не будет удалён автоматически!\nЕсли есть необходимость сделать это, либо удалите его вручную, либо поставьте аргумент can_delete_pip на True")
        print("Все зависимые библиотеки были успешно удалены!")

    def __init__(self, target_libs: set, init_at_start: bool = True) -> None:
        self.libraries_needed = target_libs
        if init_at_start: self.init_libs()