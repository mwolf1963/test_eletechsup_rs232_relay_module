#author: mwolf
#date: 20251026
#desc: input the desired hex into line 6. the console will output the two floats that should pack into the target byte
#array correctly to control the relay. could make a console app that takes argsv to do this.... but why...

import struct

target = bytes.fromhex('55560000000201AE')
f1, f2 = struct.unpack('<ff', target)
print(f"Float 1: {f1!r}")
print(f"Float 2: {f2!r}")