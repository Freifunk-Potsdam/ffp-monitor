{% macro link( url, text, target='' ) %}
    <a href="{{ url }}" target="{{ target }}">{{ text }}</a>
{% endmacro %}

{% macro ffiplist( ipl, sep='<br>', linkif=None ) %}
    {% for ip in ipl %}
        {% if linkif and linkif( ip ) %}
            {{ link( "http://%s/" % ip, ip, "_blank" ) }}
        {% else %}
            {{ ip }}
        {% endif %}
        {% if not loop.last %}
            {{ sep }}
        {% endif %}
    {% endfor %}
{% endmacro %}

