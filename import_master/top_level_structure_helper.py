
#
# (0) dependencies and imports
#
import os
import re
import sys
from pathlib import Path
import pandas as pd
import shutil

#
# 1. definition of main class
#
class TopLevelStructureHelper:
    """
    A class to help identify the top level folder structure of a project.
    It helps to fix the folder drift problem.
    Provides a solution to the problem of folder drift based on symbolic links. 
    """

    #
    def __init__(self, helper_location=None):

        #
        try:
            self.helper_location = Path(__file__).resolve().parent
        except NameError:  # __file__ is not available in Jupyter notebooks
            raise EnvironmentError("This class cannot be instantiated in an environment where __file__ is not defined, unless a 'helper_location' is provided.")
        #
        self.df_init_files = pd.DataFrame()
        self.modules_level = self.guess_modules_level()
        self.statements, self.subdirs = self.poll_opinions_on_top_level_folder_structure()
        self.believed_top_level_folder_structure = self.guess_believed_top_level_folder_structure()

    #
    def guess_believed_top_level_folder_structure(self, min_count=10):
        """
         (1) Gather all import statements and subdirectories using selg.statements and self.subdirs
         (2) Filter out the parts of import statements that are not relevant to the hierarchy of folders.
         (3) Guess and return the hierarchical structure of top level folders.
        Breaks after at most 5 iterations.
        """

        # Gather all import statements and subdirectories
        import_statements, subdirs = self.statements.values() , self.subdirs
        #subdirs = [_ for _ in subdirs if _ not in ['scripts']] 

        # A dictionary to store the counts
        counts = {}
        for statement in import_statements:
            for i, subdir in enumerate(statement):
                # if a sub dir is in the string and it's not the first element
                if subdir in subdirs and i != 0:
                    # Get the preceding name in the list
                    parent_folder = statement[i-1]

                    # Feed a count for the apparent parent folder
                    if parent_folder not in counts:
                        counts[parent_folder] = 1
                    else:
                        counts[parent_folder] += 1

        # Find the parent folder with the max count
        max_count_folder = max(counts, key=counts.get)

        # Initialize top level structure
        top_level_structure = [max_count_folder]

        # Counter for the while loop
        counter = 0

        # While loop until max_count_folder is not preceded by any other folder or counter reaches 5
        while counter < 5:
            counts = {}
            for statement in import_statements:
                for i, folder in enumerate(statement):
                    if folder == max_count_folder and i != 0:
                        parent_folder = statement[i-1]
                        if parent_folder not in counts:
                            counts[parent_folder] = 1
                        else:
                            counts[parent_folder] += 1

            if counts and max(counts.values())>min_count :
                # Update max_count_folder with its parent folder
                max_count_folder = max(counts, key=counts.get)
                # Append max_count_folder to the structure
                top_level_structure.append(max_count_folder)
                #print(counts)
                #print(top_level_structure)
            else:
                # Break the loop if max_count_folder is not preceded by any other folder
                break

            # Increment the counter
            counter += 1
        return top_level_structure[::-1]  # Reverse the list to present it from top to bottom

    #
    def poll_opinions_on_top_level_folder_structure(self):
        """
        (1) Gather all "from ... import ..." statements from .py files in the self.modules_level directory and subdirectories.
        (2) filters to statements that reference subdirectories of self.modules_level -> which point to the top level folder structure
        (3) return all the relevant import statements and the list of subdirectories.
        """
    
        # Get the current directory
        current_dir = self.modules_level
        top_level_dir = current_dir
    
        # Get the names of all direct subdirectories of top_level_dir
        subdirs = [d for d in os.listdir(top_level_dir) if os.path.isdir(os.path.join(top_level_dir, d))]
    
        # This will store all the relevant import statements
        import_statements = []
    
        # Walk through all directories and files under top_level_dir
        for root, _, files in os.walk(top_level_dir):
            for filename in files:
                # Only look at .py files
                if filename.endswith('.py'):
                    with open(os.path.join(root, filename), 'r', encoding='utf-8', errors='ignore') as file:  # Modified line
                        # Read the file content
                        content = file.read()
    
                        # Find all "from ... import ..." statements
                        from_import_matches = re.findall(r"from\s+(\S+)\s+import", content)
    
                        # Only keep the ones that reference one of the subdirectories
                        for match in from_import_matches:
                            for subdir in subdirs:
                                if subdir in match:
                                    # Split at the subdir and keep only the portion before it
                                    truncated_match = match.split(subdir)[0]+"."+subdir
                                    import_statements.append(truncated_match)
    
        import_statements = {statement: statement.split('.') for statement in import_statements if "" not in statement.split('.')}
        return import_statements, subdirs

    #
    def guess_modules_level(self, max_levels_up=3):
        """
        Attempts to identify the folder level where the modules are located
        (1) if positions in self.helper_location (the location of the same file)
        (2) it list the parent folder up to max_levels_up
        (3) for each folder, it dict-counts the number of __init__ files in the current folder, and in the subfolders one level down
        (4) assemble a pandas.DataFrame with the counts, create a rank column, stores the dataframe in self.df_init_files 
        (5) returns the folder path with the highest rank
        """
        df = []
        for level in range(-1, max_levels_up):  
            if level == -1:  
                current_path = self.helper_location.parent
            else:  
                # Ensure we do not go beyond available parent directories
                try:
                    current_path = self.helper_location.parents[level]
                except IndexError:
                    break
    
            init_files_in_current = len(list(current_path.glob("__init__.py")))
            init_files_in_children = sum(len(list(child.glob("__init__.py"))) for child in current_path.iterdir() if child.is_dir())
            df.append((str(current_path), init_files_in_current, init_files_in_children))
    
        self.df_init_files = pd.DataFrame(df, columns=['path', 'current_init_files', 'children_init_files'])
        self.df_init_files['rank'] = self.df_init_files['current_init_files'] + self.df_init_files['children_init_files']
        self.df_init_files = self.df_init_files.sort_values(by='rank', ascending=False)
        max_rank_path = self.df_init_files.sort_values(by='rank', ascending=False).iloc[0]['path']
        return Path(max_rank_path)

    #
    def detect_top_folder_structure_drift(self):
        """
        (1) Detect if the actual folder structure of the project has drifted from the believed top level folder structure
        (2) If a drift is detected, suggest he creation of a symbolic link to correct it.
        """

        # Get the believed top level folder structure
        believed_top_level_structure = self.believed_top_level_folder_structure

        # Convert top_level_structure to a path, being aware of the OS
        if os.name == 'nt':  # For Windows
            intended_path = os.path.join(os.environ["HOMEPATH"], *believed_top_level_structure)
        else:  # For Unix/Linux/MacOS
            intended_path = os.path.join("/", *believed_top_level_structure)

        # Initialize the current directory as the absolute path of the module level
        current_dir = os.path.abspath(self.modules_level)
        #return  current_dir

        # Check each folder in the top level structure against the parent folders of the current directory
        
        print(f"Checking if the top level folder structure  '{current_dir}' matches the believed top level folder structure '{intended_path}'")
        
        for folder in reversed(believed_top_level_structure):
            # Get the name of the current parent folder
            parent_folder = os.path.basename(current_dir)

            # If the parent folder doesn't match the current folder in the structure,
            # report the discrepancy, suggest the creation of a symbolic link, and return False
            if parent_folder != folder:
                print(f"Project structure drift detected. Expected parent folder '{folder}', got '{parent_folder}'.")
                print(f"Suggested action: Run self.create_structure_and_symlink() to create the folder structure and the symbolic link from '{intended_path}' to '{current_dir}'.")
                return True

            # If the parent folder matches, go one level up for the next check
            current_dir = os.path.dirname(current_dir)

        # If all parent folders match the top level structure, return True
        return False
    
    #
    def create_structure_and_symlink(self):
        """
        Safe way to create the folder structure and the symbolic link.
        (1) locate the program in the helper_location
        (2) create the folder structure with init files, and a symlink to the project root:
            (2.1) create a folder called 'magic_universal_access' with an init file. If it exists, drop it and the symlinks inside.
            (2.2) create the folder structure with init files corresponding to the believed top level folder structure, except the last folder.
            (2.3) create a symlink to the project root in the last folder.
        (3) add the directory of the current .py file to sys.path
        """

        # Get the directory of the current .py file
        base_dir = self.helper_location
        # Create the magic_universal_access directory
        magic_dir = base_dir / 'magic_universal_access'
        
        # If magic_universal_access directory exists, remove any symbolic links and then the directory
        if magic_dir.exists():
            for item in magic_dir.iterdir():
                if item.is_symlink():
                    item.unlink()  # remove the symlink if it is a symlink
            shutil.rmtree(magic_dir)
            
        # Create the magic_universal_access directory and the __init__.py file
        os.makedirs(magic_dir, exist_ok=True)
        (magic_dir / '__init__.py').touch()
        
        # Create the folder structure and the symbolic links
        current_dir = magic_dir
        for folder in self.believed_top_level_folder_structure[:-1]:
            current_dir = current_dir / folder
            os.makedirs(current_dir, exist_ok=True)
            (current_dir / '__init__.py').touch()
            
        # Create the symlink at the last level of the believed structure
        os.symlink(self.modules_level , current_dir / self.believed_top_level_folder_structure[-1])
        
        # Add the directory of the current .py file to sys.path
        sys.path.append(str(base_dir))
        sys.path.append(str(magic_dir))

        # Print out the example import statements for the user
        base_import_path = ".".join(['magic_universal_access'] + self.believed_top_level_folder_structure)
        print(f"\nExample import statement when importing from 'magic_universal_access' directory:")
        print(f"from {base_import_path}.something_else import your_module")
    
        base_import_path = ".".join(self.believed_top_level_folder_structure)
        print(f"\nExample import statement when importing directly from project directory:")
        print(f"from {base_import_path}.something_else import your_module")
