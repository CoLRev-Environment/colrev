import datetime

class Validator():

    def is_valid_api_key(self,
                     *, 
                     api_key: str
                     ) -> bool:
        """Method to validate API key input"""

        if len(api_key) == 40 and api_key.isalnum():
            return True
        else:
            return False
        
    def is_valid_yearspan(self,
                          *,
                          yearspan: str,
                          ) -> bool:
        """Method to validate entered yearspan"""

        is_valid = True

        current_year = datetime.datetime.now().date().strftime("%Y")
        check_year = yearspan.split("-")

        for x in check_year:
            if (not x.isnumeric()) or (x > current_year) or (len(check_year) > 2):
                is_valid = False
        
        if len(check_year) == 2:
            if check_year[0] > check_year[1]:
                is_valid = False
        
        return is_valid
    

    #ID-Validierung noch einbauen? DOI, S2ID etc.
    #Namens-Validierung noch einbauen!