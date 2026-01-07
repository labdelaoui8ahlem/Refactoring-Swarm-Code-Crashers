from src.utils.filesystem import (
    read_file,
    write_file,
    list_py_files,
    read_all_py_files,
    SandboxViolationError
)

# --- READ TEST ---
print("READ FILE:")
try: 
   print(read_file("sandbox\code_bugs\bad_style.py"))
except FileNotFoundError as e:
    print("File not found, continuing:", e)
except SandboxViolationError as e:
    print("Blocked correctly:", e)


# --- LIST TEST ---
print("\nLIST PY FILES:")

files = list_py_files("code_bugs") # don't add sandbox in the path it is added automaticly 
for f in files:
    print(f)

# --- READ ALL TEST ---
print("\nREAD ALL:")
all_files = read_all_py_files("code_bugs")
for path, content in all_files.items():
    print(path, "=>", content.strip())

# --- WRITE TEST ---
print("\nWRITE FILE:")
write_file("sandbox/new_file.py", "x = 42")
print(read_file("sandbox/new_file.py"))

# --- VIOLATION TEST ---
print("\nVIOLATION TEST:")
try:
    read_file("../main.py")
except SandboxViolationError as e:
    print("Blocked correctly:", e)
