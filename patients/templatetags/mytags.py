import markdown as md
from django import template
from django.template.loader import render_to_string
from django.utils.html import format_html

register = template.Library()



@register.filter(name="index")
def index(indexable, i):
    return indexable[int(f"{i}".lower())]

@register.filter(name="bar")
def bar(indexable, argstr):
    istr, widthstr = argstr.split(',')
    i = int(istr)
    width = float(widthstr)
    total = sum(indexable)
    return width * indexable[i] / total

@register.filter(name="sum")
def mysum(indexable):
    return sum(indexable)

@register.filter(name="multiply")
def myprod(num, fac):
    return num * fac

@register.filter(name="percent")
def percent(indexable, i):
    i = int(f"{i}".lower())
    total = sum(indexable)
    if total == 0:
        return " - "
    else:
        return f"{100 * indexable[i] / total:.0f}"

@register.filter(name="hashdisplay")
def hashdisplay(string):
    num = int(string)
    byte_num = int.to_bytes(num, length=8, byteorder="big", signed=True)
    hex_str = [f"{b:02x}" for b in byte_num]
    return ":".join(hex_str)

@register.simple_tag(name="include_md", takes_context=True)
def include_md(context, template_name):
    # 'context' here isn't a dictionary, but an instance of RequestContext
    context_dict = {k: v for subdict in context.dicts for k,v in subdict.items()}
    # parse the template and fill the tags with context variables
    template = render_to_string(template_name, context=context_dict)

    html_string = md.markdown(template)
    return format_html(html_string)
