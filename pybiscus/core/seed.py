from typing import Annotated

from pydantic import Field

# numpy's generators refuse a negative seed, and Lightning's seed_everything replaces one beyond
# 32 bits with a random seed, with a mere warning: the run is then not reproducible
Seed = Annotated[int, Field(ge=0, le=2**32 - 1)]
