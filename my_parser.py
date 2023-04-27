import pyparsing as plt
from contextlib import suppress
from mel_ast import *
import inspect

"""Грамматика:
        num   -> <число>
        ident -> <идентификатор>
        group -> num | ident | '(' add ')'
        mult  -> group (('*' | '/') group)*
        add   -> mult (('+' | '-') mult)*
        bool  -> add (('==' | '!=' | '>=' | '<=' | '>' | '<') add)*
        comp -> bool (('&&' | '||' ) bool)*
        expr  -> comp
        decl  -> 'type' ident ( = expr )?
        params -> decl (, decl)*
        fn    -> 'fn' ident ( params): 'type' { state }
        return -> 'return' expr
        state -> 'input' ident | 'output' add | decl | if | while | for | ident '=' add | fn | ident(params*)
        if    -> 'if' ( comp ) { state ('else' { state) } 
        while -> 'while' ( comp ) { expr_list } 
        for   -> 'for' (decl; comp; expr) { state }
        prog  -> state*
        start -> prog
    """

def _parser():

    # Токены
    DOT = plt.Literal('.').suppress()
    LPAREN = plt.Literal('(').suppress()
    RPAREN = plt.Literal(')').suppress()
    LBRACKET = plt.Literal('[').suppress()
    RBRACKET = plt.Literal(']').suppress()
    LBRACE = plt.Literal('{').suppress()
    RBRACE = plt.Literal('}').suppress()
    COMMA = plt.Literal(',').suppress() 
    ASSIGN = plt.Literal('=').suppress()
    SEMICOLON = plt.Literal(';').suppress()

    # Литералы
    num = plt.Regex(r'\d+\.\d+|\d+(e|E)(\+|-)\d+|0x[0-9a-fA-F]+|0[0-7]+|\d+')
    char_literal = plt.QuotedString('\'', escChar='\\', unquoteResults=False, convertWhitespaceEscapes=False)
    str_literal = plt.QuotedString('"', escChar='\\', unquoteResults=False, convertWhitespaceEscapes=False)
    literal = (num | char_literal | str_literal).setName('literal')

    # Типы данных
    int_type = plt.Keyword('int')
    float_type = plt.Keyword('float')
    char_type = plt.Keyword('char')
    string_type = plt.Keyword('string')
    void_type = plt.Keyword('void')
    
    #decl_type = int_type | float_type | char_type | string_type | void_type

    # Бинарные операции
    ADD = plt.Keyword('+')
    SUB = plt.Keyword('-')
    MUL = plt.Keyword('*')
    DIV = plt.Keyword('/')
    MOD = plt.Keyword('%')
    GT = plt.Keyword('>')
    LT = plt.Keyword('<')
    GE = plt.Keyword('>=')
    LE = plt.Keyword('<=')
    EQ = plt.Keyword('==')
    NE = plt.Keyword('!=')
    AND = plt.Keyword('&&')
    OR = plt.Keyword('||')

    bool_operations = EQ | NE | GE | LE | GT | LT
    comp_and = AND
    comp_or = OR

    # Идентификатор
    ident = plt.pyparsing_common.identifier.copy().setName('ident')
    decl_type = ident.copy()

    # Группа
    add = plt.Forward()
    mult = plt.Forward()
    expression = plt.Forward()
    func_call = plt.Forward()
    group = literal | func_call | ident | LPAREN + expression + RPAREN

    # Умножение
    mult = plt.Group(group + plt.ZeroOrMore((MUL | DIV) + group)).setName('bin_op')

    # Cложение
    add << plt.Group(mult + plt.ZeroOrMore((ADD | SUB) + mult)).setName('bin_op')

    # Логические операции
    bool_op = plt.Group(add + plt.Optional(bool_operations + add)).setName('bin_op')
    comp_and_logic = plt.Group(bool_op + plt.ZeroOrMore(comp_and + bool_op)).setName('bin_op')
    comp_or_logic = plt.Group(comp_and_logic + plt.ZeroOrMore(comp_or + comp_and_logic)).setName('bin_op')

    # Полное выражение
    expression << (comp_or_logic)

    # Ввод - вывод
    #input_op = plt.Keyword('input').suppress() + ident
    #output_op = plt.Keyword('output').suppress() + expression

    statement = plt.Forward()
    statement_list = plt.Forward()

    # Присваивание переменной
    assign = ident + ASSIGN + expression
    # Объявление переменной
    decl = decl_type + ident + plt.Optional(ASSIGN + expression)

    # Объявление параметров функции
    decl_list = plt.ZeroOrMore(decl + plt.Optional(COMMA))
    func_call_params = plt.ZeroOrMore(expression + plt.Optional(COMMA))

    # Объявление тела функции (циклов, условного оператора)
    op_body = LBRACE + statement_list + RBRACE

    # Объявление функции
    func_decl = decl_type + ident + LPAREN + decl_list + RPAREN + op_body
    func_call = ident + LPAREN + func_call_params + RPAREN

    # Оператор возврата значения
    return_op = plt.Keyword('return').suppress() + plt.Optional(expression)

    # Условный оператор if
    else_block = plt.Keyword('else').suppress() + op_body
    if_op = plt.Keyword('if').suppress() + LPAREN + expression + RPAREN + op_body + plt.Optional(else_block)

    # Циклы (while, for)
    while_header = plt.Keyword('while').suppress() + LPAREN + expression + RPAREN
    while_op = while_header + op_body

    for_header = plt.Keyword('for').suppress() + LPAREN + statement_list + SEMICOLON + plt.Optional(expression) + SEMICOLON + plt.Optional(statement_list) + RPAREN
    for_op = for_header + op_body

    # Выражение
    statement << (
            func_decl |
            decl |
            if_op |
            for_op |
            while_op |
            assign |
            func_call |
            return_op + SEMICOLON)

    # Список выражений 
    statement_list << plt.ZeroOrMore(statement + plt.Optional(SEMICOLON))
    program = statement_list.ignore(plt.cStyleComment).ignore(plt.dblSlashComment) + plt.StringEnd()
    start = program

    def set_parse_action_magic(rule_name: str, parser: plt.ParserElement) -> None:
        if rule_name == rule_name.upper():
            return
        if getattr(parser, 'name', None) and parser.name.isidentifier():
            rule_name = parser.name
        if rule_name in ('bin_op', ):
            def bin_op_parse_action(s, loc, tocs):
                node = tocs[0]
                if not isinstance(node, AstNode):
                    node = bin_op_parse_action(s, loc, node)
                for i in range(1, len(tocs) - 1, 2):
                    secondNode = tocs[i + 1]
                    if not isinstance(secondNode, AstNode):
                        secondNode = bin_op_parse_action(s, loc, secondNode)
                    node = BinOpNode(BinOp(tocs[i]), node, secondNode)
                return node
            parser.setParseAction(bin_op_parse_action)
        else:
            cls = ''.join(x.capitalize() for x in rule_name.split('_')) + 'Node'
            with suppress(NameError):
                cls = eval(cls)
                if not inspect.isabstract(cls):
                    def parse_action(s, loc, tocs):
                        return cls(*tocs)
                    parser.setParseAction(parse_action)

    for var_name, value in locals().copy().items():
        if isinstance(value, plt.ParserElement):
            set_parse_action_magic(var_name, value)

    return start
    
parser = _parser()

def parse(prog: str) -> StatementListNode:
    return parser.parseString(str(prog))[0]


