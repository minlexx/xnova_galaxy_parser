function doSearchPlayerorAlliance(val, cat){
    $('#sb').searchbox('disable');
    $('#dg_result').datagrid('load', {
        ajax: 'grid',
        query: val,
        category: cat
    });
    $('#sb').searchbox('enable');
}

function load_lastlogs(val, cat) {
    console.log('load_lastlogs(): val=' + val + ', cat=' + cat);
    if( !val && !cat) {
        // called from button click, no method parameters
        var sb_lastlogs = $('#sb_lastlogs');
        val = sb_lastlogs.searchbox('getValue');
        cat = sb_lastlogs.searchbox('getName');
        // console.log('Called from button click, val = ' + val + ', cat = ' + cat);
    }
    // get textbox value (nick filter)
    nick_filter = $('#sb_nick_filter').textbox('getText');
    // console.log('got nick_filter = ' + nick_filter);
    // load data
    $('#dg_lastlogs').datagrid('load', {
        ajax: 'lastlogs',
        value: val,
        category: cat,
        nick: nick_filter
    });
    return true;
}

function on_ss_slider_change(value, oldValue) {
    $('#nn_s_min').numberbox('setValue', value[0]);
    $('#nn_s_max').numberbox('setValue', value[1]);
}

function on_nb_ss_min_change(value, oldValue) {
    var range = $('#slide_sys').slider('getValues');
    range[0] = value;
    $('#slide_sys').slider('setValues', range);
}

function on_nb_ss_max_change(value, oldValue) {
    var range = $('#slide_sys').slider('getValues');
    range[1] = value;
    $('#slide_sys').slider('setValues', range);
}

function reset_sliders() {
    var gals = [1, 5];
    var sss = [1, 499];
    $('#slide_gal').slider('setValues', gals)
    $('#slide_sys').slider('setValues', sss)
    $('#nn_s_min').numberbox('setValue', sss[0]);
    $('#nn_s_max').numberbox('setValue', sss[1]);
}

function search_inactives() {
    var c_i = $('#chk_inactive1').is(':checked') ? 'i' : '';
    var c_ii = $('#chk_inactive2').is(':checked') ? 'I' : '';
    var c_ban = $('#chk_banned').is(':checked') ? 'G' : '';
    var c_ro = $('#chk_ro').is(':checked') ? 'U' : '';
    var c_g1 = $('#chk_g1').is(':checked') ? '1' : '';
    var c_g2 = $('#chk_g2').is(':checked') ? '2' : '';
    var c_g3 = $('#chk_g3').is(':checked') ? '3' : '';
    var c_g4 = $('#chk_g4').is(':checked') ? '4' : '';
    var c_g5 = $('#chk_g5').is(':checked') ? '5' : '';
    var s_range = $('#slide_sys').slider('getValues');
    var min_rank = $('#nn_min_rank').numberbox('getValue');
    var flags = '' + c_i + c_ii + c_ban + c_ro;
    var gals = c_g1 + c_g2 + c_g3 + c_g4 + c_g5;
    var s_min = s_range[0];
    var s_max = s_range[1];
    //alert('flags=' + flags + ' gals=' + gals + ' [' + s_min + '-' + s_max + ']'
    //    + ' min_rank=' + min_rank
    //    + '\nПока не работает, но будет!');
    $('#dg_result').datagrid('load', {
        ajax: 'grid',
        category: 'inactives',
        user_flags: flags,
        gals: gals,
        s_min: s_min,
        s_max: s_max,
        min_rank: min_rank
    });
}

// $('#chk_inactive1').is(':checked')

// ajax requesting status of background DB update process from json file
window.g_dbupdate_ajax_in_progress = false;
window.g_dbupdate_jqXHR = null;

function request_dbupdate_progress() {
    if (window.g_dbupdate_ajax_in_progress) {
        return false;
    }
    window.g_dbupdate_ajax_in_progress = true;
    //if (console && console.log) {
    //    console.log('Sending request to get progress of db update...');
    //}
    window.g_dbupdate_jqXHR = $.ajax({
        method: 'GET',
        url: 'galaxy_auto_parser5.json',
        cache: false,
        dataType: 'json',
        success: on_dbupdate_progress_request_success,
        error: on_dbupdate_progress_request_error
    });
}

function on_dbupdate_progress_request_success(data) {
    window.g_dbupdate_ajax_in_progress = false;
    window.g_dbupdate_jqXHR = null;
    var done = data.done;
    var total = data.total;
    var position = data.position;
    var percent = 100;
    if (total > 0) {
        percent = Math.ceil(100.0 * done / total);
        if (percent > 100) {
            percent = 100;
        }
        if (percent < 0) {
            percent = 0;
        }
        $('#p_dbupdate').progressbar('setValue', percent);
        $('#p_dbupdate_pos').html('&nbsp;&nbsp; ' + position);
    }
    //if (console && console.log) {
    //    console.log('on_dbupdate_progress_request_success(): ');
    //    console.log(data);
    //}
    window.setTimeout( request_dbupdate_progress, 5000 );
}

// Type: Function( jqXHR jqXHR, String textStatus, String errorThrown )
function on_dbupdate_progress_request_error( jqXHR, textStatus, errorThrown ) {
    window.g_dbupdate_ajax_in_progress = false;
    window.g_dbupdate_jqXHR = null;
    if (console && console.log) {
        console.log('on_dbupdate_progress_request_error(): ');
        console.log(textStatus);
    }
}
