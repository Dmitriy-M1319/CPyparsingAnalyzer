import os
import sys
import my_parser
import code_gen

import my_semantic_baza


def main():
    prog = '''
        void foo(int a) {
            if (a != 2) {
                a = a + 1;
            }
        }

        foo(5);
        string str = "Hello";
        char c = 'a';
        int a = 1;
        int s;
        for(int i = 1; i < 7; i = i + 1) { 
            s = 7; 
        }
        while (a != 7) {
            int b;
            b = a;
        }

        if (a > 5) {
            a = 5;
        }
    '''

    prog2 = '''
        int a = 5;
    '''
    
    prog1 = my_parser.parse(prog)
    print(prog1)
    print(*prog1.tree, sep=os.linesep)
    #try:
    scope = my_semantic_baza.prepare_global_scope()
    prog1.semantic_check(scope)
    print(*prog1.tree, sep=os.linesep)
    #except my_semantic_baza.SemanticException as e:
     #    print('Ошибка: {}'.format(e.message), file=sys.stderr)
      #   exit(2)

    gen = code_gen.CodeGenerator()
    gen.msil_gen_program(prog1)
    print(*gen.code, sep=os.linesep)



if __name__ == "__main__":
    main()
