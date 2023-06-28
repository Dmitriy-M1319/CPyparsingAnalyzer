import os
import sys
import my_parser
import code_gen
import argparse

import my_semantic_baza


def main1():
    parser = argparse.ArgumentParser(description='Compiler demo program (msil)')
    parser.add_argument('src', type=str, help='source code file')
    parser.add_argument('--msil-only', default=False, action='store_true', help='print only msil code (no ast)')
    args = parser.parse_args()

    with open(args.src, mode='r') as f:
        prog = f.read()
    
    prog1 = my_parser.parse(prog)
    if not args.msil_only:
        print(prog1)
        print(*prog1.tree, sep=os.linesep)
    try:

        scope = my_semantic_baza.prepare_global_scope()
        prog1.semantic_check(scope)
    except my_semantic_baza.SemanticException as e:
        print('Ошибка: {}'.format(e.message), file=sys.stderr)
        exit(2)
    if not args.msil_only:
        print(*prog1.tree, sep=os.linesep)
    if not args.msil_only:
        print(" ")
        print("msil:")
    gen = code_gen.CodeGenerator()
    gen.msil_gen_program(prog1)
    print(*gen.code, sep=os.linesep)


def main():
    prog = '''
        int main(int argc) {
            int a[3] = {1, 2, 3};
            int k = a[2];
            a[3] = 0;
            return 0;
        }
    '''
    
    prog1 = my_parser.parse(prog)
    print(prog1)
    print(*prog1.tree, sep=os.linesep)
    # scope = my_semantic_baza.prepare_global_scope()
    print()
    print('Семантический анализ:')
    try:
        scope = my_semantic_baza.prepare_global_scope()
        prog1.semantic_check(scope)
        print(*prog1.tree, sep=os.linesep)
    except my_semantic_baza.SemanticException as e:
        print('Ошибка: {}'.format(e.message), file=sys.stderr)
        exit(2)


if __name__ == "__main__":
    main()
