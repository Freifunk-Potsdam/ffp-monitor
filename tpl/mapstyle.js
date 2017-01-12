function(feature, resolution){
    var type = feature.getGeometry().getType();
    var props = feature.getProperties();
    var color = function( state ){
        if (state == 'online') return '#00EE00'
        else if (state == 'late') return '#FFFF00'
        else if (state == 'offline') return '#FF0000'
        else if (state == 'dead') return 'rgba(55,55,55,0.5)'
        else if (state == 'unreachable') return '#AAAAFF'
        else if (state == 'selected') return '#3333FF'
        else return '#FFFFFF';
    };
    var lcolor = function( etx ){
        if (etx > 10) return '#BB3333'
        else if (etx > 4 ) return '#FF6600'
        else if (etx > 2 ) return '#FFCB05'
        else return '#00CC00';
    };
    var rcolor = function( etx, maxetx ){
        var r = Math.floor( ( etx / maxetx ) * 255 );
        var g = Math.floor( 255 - ( etx / maxetx ) * 255 );
        return 'rgb('+r+','+g+",0)"
    };
    if (type == "Point" && props['uplink']) {
        var style = new ol.style.Style({
            image: new ol.style.RegularShape({
                points: 3,
                fill: new ol.style.Fill({ color: color( props['state'] ) }),
                stroke: new ol.style.Stroke({ color: '#222222' }),
                radius: 1.5 * Math.max(3,Math.min(10/Math.sqrt(resolution),10))
            })
        });
        return style;
    } else if (type == "Point" && ! props['uplink']) {
        var style = new ol.style.Style({
            image: new ol.style.Circle({
                fill: new ol.style.Fill({ color: color( props['state'] ) }),
                stroke: new ol.style.Stroke({ color: '#222222' }),
                radius: Math.max(3,Math.min(10/Math.sqrt(resolution),10))
            })
        });
        return style;
    } else if (type == "LineString" && 'maxetx' in props) {
        var style = new ol.style.Style({
            stroke: new ol.style.Stroke({
                color: rcolor( props["etx"], props["maxetx"] ),
                width: Math.max(1,Math.min(4/resolution,3))
            })
        });
        return style;
    } else if (type == "LineString") {
        var style = new ol.style.Style({
            stroke: new ol.style.Stroke({
                color: lcolor( props['etx'] ),
                width: Math.max(1,Math.min(4/resolution,3))
            })
        });
        return style;
    }
}
