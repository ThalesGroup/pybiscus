
from typing import List

import numpy as np


class ResultModifier:

    def modify(
        self,
        round: int,
        cid: str, 
        weights: List[np.ndarray],
    ) -> List[np.ndarray]:

        pass
    