class FileSystem:
    def __init__(self, file_path):
        self.file_path = file_path

    def remove(self, content):
        lines = self.read()
        lines__ = [line for line in lines if content not in line]
        with open(self.file_path, 'w') as file:
            file.writelines(lines__)

    def read(self):
        with open(self.file_path, 'r') as file:
            return file.readlines()

    def add(self, line):
        with open(self.file_path, 'a') as file:
            file.write(line + '\n')
