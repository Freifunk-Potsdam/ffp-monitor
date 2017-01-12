{% macro link( url, text, target='', title='' ) %}
    <a href="{{ url }}" target="{{ target }}" title="{{ title }}">{{ text }}</a>
{% endmacro %}

{% macro ffiplink( ip, tmp = '' ) %}
    {% if ips.isffip( ip ) %}
        {{ link( "http://%s/" % ip, ip, "_blank", ips.ffhostname( ip ) ) }}
    {% else %}
        {{ ip }}
    {% endif %}
{% endmacro %}

{% macro ffiplist( ipl, sep='<br>' ) %}
    {% for ip in ipl %}
        {{ ffiplink( ip ) }}
        {% if not loop.last %}
            {{ sep }}
        {% endif %}
    {% endfor %}
{% endmacro %}

{% macro formatDuration( s ) %}
    {% set d = s // (24 * 60 * 60) %}
    {% set s = s % (24 * 60 * 60) %}
    {% set h = s // (60 * 60) %}
    {% set s = s % (60 * 60) %}
    {% set m = s // 60 %}
    {% set s = s % 60 %}
    {{ "%dd" % d if d > 0 else '' }}
    {{ "%dh" % h if h > 0 else '' }}
    {{ "%dm" % m if m > 0 else '' }}
    {{ "%ds" % s if s > 0 else '' }}
{% endmacro %}

{% macro formatMeters( m ) %}
    {% if m > 1000 %}
        {{ (m / 1000)|round(1) }} km
    {% else %}
        {{ m|int }} m
    {% endif %}
{% endmacro %}
