import pandas as pd
from typing import List

def coalesce(s: pd.Series, *series: List[pd.Series]):
    for other in series:
        s = s.mask(pd.isnull, other)        
    return s
