import sys
import builtins

orig_print = builtins.print
def my_print(*args, **kwargs):
    orig_print(*args, **kwargs)
    if any("Loading" in str(a) for a in args) or any("Special" in str(a) for a in args):
        import traceback
        traceback.print_stack()

builtins.print = my_print

import transformers
import logging
logging.basicConfig(level=logging.INFO)

# Hook into hugging face logger
logger = logging.getLogger("transformers")
orig_info = logger.info
def my_info(msg, *args, **kwargs):
    orig_info(msg, *args, **kwargs)
    import traceback
    traceback.print_stack()
logger.info = my_info
logger.warning = my_info

print("Importing main...")
import main
print("Main imported!")
