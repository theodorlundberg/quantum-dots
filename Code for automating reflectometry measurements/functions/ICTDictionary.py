import pandas as pd

class Dictionary:
    def __init__(self, dictName):
        '''
        Makes or loads a dictionary.
        
        Args:
            dictName: string, filename of dictionary
        '''
        self.name = dictName # string
        try:
            self.dict = pd.read_csv(dictName + '.csv', header=[0,1], index_col=0).rename(columns=int).to_dict()
        except FileNotFoundError:
            print('We found no file with the name %s! An empty dictionary has been prepared in stead.' %(dictName + '.csv'))
            self.dict = {}
    
    def save(self):
        '''
        Save dictionary to csv.
        '''
        df = pd.DataFrame(self.dict)
        df = df.reindex(sorted(df.columns), axis=1)
        df.to_csv(self.name + '.csv')
    
    def addICT(self, ICTnumber, ICTcentre):
        '''
        Adds or updates the coordinates of an ICT to the dictionary.
        
        Args:
            ICTnumber: tuple of length 2 in the format (G1_electronNo, G2_electronNo)
            ICTcentre: tuple of length 4 in the format (G1_centre, G1_length, G2_centre, G2_length)
        '''
        if ICTnumber in self.dict:
            preexistingICT = True
        else:
            preexistingICT = False
            
        if type(ICTnumber) == tuple and len(ICTnumber) == 2:
            if type(ICTcentre) == tuple and len(ICTcentre) == 4:
                self.dict[ICTnumber] = {'G1_centre' : ICTcentre[0], 'G1_length' : ICTcentre[1], 'G2_centre' : ICTcentre[2], 'G2_length' : ICTcentre[3]}
            else:
                print('Unlawful input. ICTcentre must be a tuple of length 4 in the format (G1_centre, G1_length, G2_centre, G2_length)')
        else:
            print('Unlawful input. ICTsize must be a tuple of length 2 in the format (G1_electronNo, G2_electronNo)')
        
        self.save()
        
        if not preexistingICT:
            print('ICT %s has been successfully added to the %s dictionary with values %s' %(ICTnumber, self.name, ICTcentre))
        else:
            print('ICT %s has been successfully updated in the %s dictionary with values %s' %(ICTnumber, self.name, ICTcentre))

            
