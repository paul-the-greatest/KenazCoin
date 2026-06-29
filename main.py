#demo only. not usable

import os
import sys

#this one is just a demo, do not consider it. 
#run cli if you want to test 

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from coin.app.main import main


if __name__ == "__main__":
    main()
