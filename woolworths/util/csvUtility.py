import csv
import os

class CsvUtil:
    def __init__(self, csvfilename):
        self.csvfilename = csvfilename
        self.dir = os.path.dirname(os.path.abspath(__file__)) # dir of this file
        self.path = os.path.join(self.dir, "util", self.csvfilename)

        if not (os.path.exists(self.path)):
            with open(self.path, "w", newline="") as file:
                pass


        self.actions = {
            "readAndFillSet": self._readAndFillSet,
            "printElements": self._printElements
        }

    def actionList(self):
        print(self.actions.keys())

    def readCSV(self, actionKey):
        with open(self.path, "r", newline="") as file:
            reader = csv.reader(file)
            for row in reader:
                return self.actions[actionKey](reader)

    def _readAndFillSet(self, reader):
        s = set()
        for row in reader:
            if(row):
                s.add(row[0]) # first col
        return s;
        
    def _printElements(self, reader):
        for row in reader:
            print(row)


    def writeCSV(self, data, option="a"):
        if(option=="r"):
            print("wrong method")
            return
        with open(self.path, option, newline="") as file:
            writer = csv.writer(file)
            writer.writerow(data)

    
    def testing(self):
        print(self.path)


# utl = CsvUtil("testcsv.csv")
# for e in utl.readCSV("readAndFillSet"):
# #     print(e)
# utl.writeCSV(["testing", "helloworld", "asdf"], "r")