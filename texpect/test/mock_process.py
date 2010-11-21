'''
@author: shylent
'''
import sys

if __name__ == '__main__':
    sys.stdout.write('hello')
    sys.stdout.flush()
    sys.stdin.read()
    sys.stdout.write('farewell')
    sys.exit(0)
