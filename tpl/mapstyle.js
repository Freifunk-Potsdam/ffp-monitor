function(feature, resolution){
    var type = feature.getGeometry().getType();
    var props = feature.getProperties();
    var ap_colors = [
        [       15*60,   0, 238,  0, 1.0 ],
        [     3*60*60, 255, 255,  0, 1.0 ],
        [    24*60*60, 255,   0,  0, 1.0 ],
        [ 35*24*60*60,  55,  55, 55, 0.5 ],
        [100*24*60*60,  55,  55, 55, 0.2 ]
    ];
    var etx_colors = [
        [  1,   0, 204,   0, 1 ],
        [  2, 255, 204,   0, 1 ],
        [  4, 255, 102,   0, 1 ],
        [ 10, 187,  51,  51, 1 ]
    ];
    var color = function( state ){
        if (state == 'online') return '#00EE00'
        else if (state == 'late') return '#FFFF00'
        else if (state == 'offline') return '#FF0000'
        else if (state == 'dead') return 'rgba(55,55,55,0.5)'
        else if (state == 'unreachable') return '#AAAAFF'
        else if (state == 'selected') return '#3333FF'
        else return '#FFFFFF';
    };
    var icolor = function( value, colors ){
        if (value <= colors[0][0]) {
            return "rgba(" + colors[0].slice(1).join() + ")";
        } else if (value >= colors[colors.length-1][0]) {
            return "rgba(" + colors[colors.length-1].slice(1).join() + ")";
        }
        for (i=0; i<colors.length-1; i++) {
            if (value >= colors[i][0] && value <= colors[i+1][0]) {
                f = (value - colors[i][0]) / (colors[i+1][0] - colors[i][0]);
                c = [];
                for (j=1; j<5; j++){
                    c.push( colors[i][j] + (colors[i+1][j] - colors[i][j]) * f );
                }
                return "rgba(" + c.join() + ")";
            }
        }
    };
    var lcolor = function( etx ){
        if (etx > 10) return '#BB3333'
        else if (etx > 4 ) return '#FF6600'
        else if (etx > 2 ) return '#FFCC00'
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
                fill: new ol.style.Fill({ color: icolor( props['last_data'], ap_colors ) }),
//                fill: new ol.style.Fill({ color: color( props['state'] ) }),
                stroke: new ol.style.Stroke({ color: '#222222' }),
                radius: 1.5 * Math.max(3,Math.min(10/Math.sqrt(resolution),10)) * (props['state']=='dead' ? 0.5 : 1.0)
            })
        });
        return style;
    } else if (type == "Point" && ! props['uplink']) {
        var style = new ol.style.Style({
            image: new ol.style.Circle({
                fill: new ol.style.Fill({ color: icolor( props['last_data'], ap_colors ) }),
//                fill: new ol.style.Fill({ color: color( props['state'] ) }),
                stroke: new ol.style.Stroke({ color: '#222222' }),
                radius: Math.max(3,Math.min(10/Math.sqrt(resolution),10)) * (props['state']=='dead' ? 0.5 : 1.0)
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
                color: icolor( props['etx'], etx_colors ),
//                color: lcolor( props['etx'] ),
                width: Math.max(1,Math.min(4/resolution,3))
            })
        });
        return style;
    }
}
