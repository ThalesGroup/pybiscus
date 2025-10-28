
def ensure_dir_exists(path):
    path.mkdir(parents=True, exist_ok=True)

# for a file : create the parent directory
def ensure_file_dir_exists(file_path):
    ensure_dir_exists(file_path.parent)

