import os
import sys
import my_parser

import my_checker
import my_semantic_baza


def main():
    prog = '''
        void foo(int a) {
            if (a != 2) {
                a = a + 1;
            }
        }

        int a = 5;
        foo(a);
        string str = "Hello";
        char c = 'a';
        int i;
        for (; ; ) { 
            s = 7; 
        }
        while (a != 7) {
            int b;
            b = a;
        }

        if (a > 5) {
            return 0;
        }
    '''
    
    prog1 = my_parser.parse(prog)
    print(prog1)
    print(*prog1.tree, sep=os.linesep)
    try:
        checker = my_checker.SemanticChecker()
        scope = my_checker.prepare_global_scope()
        checker.semantic_check(prog1, scope)
        print(*prog1.tree, sep=os.linesep)
        print()
    except my_semantic_baza.SemanticException as e:
        print('Ошибка: {}'.format(e.message), file=sys.stderr)
        exit(2)



if __name__ == "__main__":
    main()
