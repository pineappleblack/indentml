from indentml.parser import QqTag, QqParser
from copy import deepcopy

# Набор служебных слов
keys = ['tag', 'follow']


# Собирает теги, объявленные в данной грамматике
def collect_allowed_tags(gram_list):
    tag_list = []

    # Для всех элементов, кроме первого, потому что первый _root или ключевое слово (tag)
    for el in gram_list[1:]:
        # Если элемент списка — строка (название тега), добавлять его к списку тегов
        if isinstance(el, str):
            tag_list.append(el)
        # Иначе — поиск названий тегов внутри списка и добавление их к списку тегов
        else:
            tag_list += collect_allowed_tags(el)

    return tag_list


# Переводит грамматику в вид
# [
#     [
#         {
#             'name': 'tag0',
#             'type': 'tag'
#          },
#         [
#           [
#             {
#                 'name': 'tag1',
#                 'type': 'tag'
#             },
#           ]
#           [
#             {
#                 'name': 'tag2',
#                 'type': 'tag'
#             }
#           ]
#         ]
#     ]
# ]
# Где список подразумевает содержание тега, а словарь содержит служебную информацию
# соответствует
# \tag0
#     \tag1
#     \tag2
def gram_to_object(gram_list):
    obj = []

    # Для каждого элемента списка
    for i, el in enumerate(gram_list):
        # Если это строка, и она есть в списке служебных слов, добавлять к массиву ответа элемент с name и type
        if isinstance(el, str):
            if el in keys:
                obj.append({'name': gram_list[i+1], 'type': gram_list[i]})
        # Если это массив, применять функцию к нему, и добавлять результат к массиву ответа
        else:
            obj.append(gram_to_object(el))

    return obj

# Проверяет наличие тега в КОРНЕ части грамматики
def check_pair(tag_name, gram_part):

    # Для каждого элемента в КОРНЕ грамматики
    for el in gram_part:
        # Если этот элемент является списком
        if isinstance(el, list):
            # И его имя совпадает с проверямым тегом, тег валиден!
            if el[0]['name'] == tag_name:
                return 1
    return 0


# Проверяет валидность каждой ветки дерева
def validate(doc_list, gram_obj, allowed_tags, full_gram = []):

    if full_gram == []:
        full_gram = gram_obj

    validation_result = []

    last_head = ''

    # Для каждого тега в дереве-списке документа
    for el in doc_list:
        # Если это строка
        if isinstance(el, str):
            # и она есть в списке служебных слов
            # запомнить тег, с которого начинать проверку (уровень вложенности)
            # проверить валидность текущего тега
            if el in allowed_tags:
                last_head = el
                validation_result.append(check_pair(el, gram_obj))
            # если её там нет — это просто строка, результат проверки — истина
            else:
                validation_result.append(1)
        # Если же это массив (то есть, внутри вложен тег)
        else:
            # Если это начало дерева, передать всю грамматику
            if last_head == '':
                gram_part = gram_obj
            # Если же нет — отсечь ту её часть, которая начинается с текущего уровня вложенности
            else:
                gram_part = []
                for gram_tag in gram_obj:
                    if isinstance(gram_tag, list):
                        if gram_tag[0]['name'] == last_head:
                            gram_part = gram_tag
                            break

            # Если в корне встречается follow, заменить ссылку на реальные теги
            for i in range(len(gram_part)):
                if isinstance(gram_part[i], list):
                    if gram_part[i][0]['type'] == 'follow':
                        for j in range(len(full_gram)):
                            if isinstance(full_gram[j], list):
                                if (full_gram[j][0]['type'] == 'tag') \
                                and (full_gram[j][0]['name'] == gram_part[i][0]['name']):
                                    gram_part[i] = full_gram[j][1]

            # Проверить все вложенные теги
            validation_result.append(validate(el, gram_part, allowed_tags, full_gram))

    return validation_result


# Парсинг грамматики
with open('test-grammar.qq') as f:
    grammar = f.read()

myParser = QqParser(allowed_tags=set(keys))
tree = myParser.parse(grammar)
gram_list = tree.as_list()

# Создание списка разрешённых тегов
allowed_tags = collect_allowed_tags(gram_list)

# Парсинг документа
with open('test-text.txt') as f:
    text = f.read()

my_text_parser = QqParser(allowed_tags=set(allowed_tags))
tree = my_text_parser.parse(text)
doc_list = tree.as_list()

# Валидация
gram_obj = gram_to_object(gram_list)
validation_result = validate(doc_list, gram_obj, allowed_tags)

print(gram_obj)
print(doc_list)
print(validation_result)
