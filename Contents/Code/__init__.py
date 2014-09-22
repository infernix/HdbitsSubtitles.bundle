#hdbits.org

import string, os
#import simplejson as json
import string
import zipfile
import time
import shutil
import tempfile


# TODO: put in checks to ensure we have a valid unrar(.exe)
# TODO: Use the global dict() function to store credential verification state.
# TODO: add preferences to skip commentary and/or SDH and/or forced

# We need rarfile.py as many subtitle archives are in rar files.
import rarfile
# The jailed path is relative under "Plug-in Support/Data/com.plexapp.agents.hdbits/
# unrar should probably be placed there by the user
rarfile.UNRAR_TOOL = os.getcwd() + "/unrar"

# NO TRAILING SLASH
HDBITS_URL = "https://hdbits.org"

# timeout
apitimeout = 30

OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

# Mapping HDBits language codes to ISO
langPrefs2HDbits = {'eng':'uk', 'swe':'se', 'ara':'ar', 'bul':'bg', 'chi':'cn', 'hrv':'hr', 'cze':'cz', 'dan':'dk', 'dut':'nl', 'est':'ee', 'fin':'fi', 'fre':'fr', 'ger':'de', 'gre':'gr', 'heb':'il', 'hun':'hu', 'ita':'it', 'jpn':'jp', 'kor':'kr', 'nor':'no', 'pol':'pl', 'por':'pt', 'ron':'ro', 'rus':'ru', 'srp':'cs', 'slo':'sk', 'slv':'si', 'spa':'es', 'tur':'tr'}

#Find these in the DefaultPrefs.json and http://dev.plexapp.com/docs/api/localekit.html#locale-language
langPrefs2Plex = {'eng':'en', 'swe':'sv', 'ara':'ar', 'bul':'bg', 'chi':'zh', 'hrv':'hr', 'cze':'cs', 'dan':'da', 'dut':'nl', 'est':'et', 'fin':'fi', 'fre':'fr', 'ger':'de', 'gre':'el', 'heb':'he', 'hun':'hu', 'ita':'it', 'jpn':'ja', 'kor':'ko', 'nor':'no', 'pol':'pl', 'por':'pt', 'ron':'ro', 'rus':'ru', 'srp':'sr', 'slo':'sk', 'slv':'sl', 'spa':'es', 'tur':'tr'}

# Mapping full languages to ISO for language guessing
langGuess = { 'eng':'english', 'swe':'swedish', 'ara':'arabic', 'bul':'bulgarian', 'chi':'chinese', 'hrv':'hrvatski', 'cze':'czech', 'dan':'danish', 'dut':'dutch', 'est':'estonian', 'fin':'finnish', 'fre':'french', 'ger':'german', 'gre':'greek', 'heb':'hebrew', 'hun':'hungarian', 'ita':'italian', 'jpn':'japanese', 'kor':'korean', 'nor':'norwegian', 'pol':'polish','por':'portuguese', 'ron':'romanian', 'rus':'russian', 'srp':'serbian', 'slo':'slovak', 'slv':'slovenian', 'spa':'spanish', 'spa':'espagnol', 'tur':'turkish', 'vie':'vietnamese' }

# Some additional custon guessing patterns, mmay be extended
langGuessShort = { 'jpn':'jap', 'srp':'serb', 'spa':'esp'  }

# list of patterns to skip in archives. These are not regexes, just word matches.
badfilenames = ['MACOSX']

def ValidatePrefs():
    logprefix = 'ValidatePrefs(): '
    Log.Debug(logprefix + 'Checking credentials')
    if not Prefs['username'] or not Prefs['passkey']:
        msg = 'Missing credentials, cannot proceed'
        Log.Error(logprefix + msg)
        return ObjectContainer(header='Error',message=msg)
    apiurl = HDBITS_URL + "/api/test"
    query = {  "username": Prefs['username'], "passkey":Prefs['passkey']}
    postdata = JSON.StringFromObject(query)
    try:
        response = HTTP.Request(apiurl, data=postdata, timeout=apitimeout,cacheTime=3600)
    except:
        msg = "Unknown error while querying API"
        Log.Exception(logprefix + msg)
        return ObjectContainer(header='Error',message=msg)
    try:
        jsondata = JSON.ObjectFromString(response.content)
    except ValueError, e:
        msg =  "ValueError parsing results: " + str(e)
        Log.Exception(logprefix + msg)
        return ObjectContainer(header='Error',message=msg)
    if 'status' in jsondata:
        if jsondata['status'] == 5:
            msg = 'Invalid credentials: ' + str(jsondata['message'])
            Log.Error(logprefix + msg)
            return ObjectContainer(header='Error', message=msg)
        elif jsondata['status'] == 4:
            msg = 'Credentials missing?'
            Log.Error(logprefix + msg)
            return ObjectContainer(header='Error', message=msg)
        elif jsondata['status'] == 3:
            msg = 'JSON error: ' + str(jsondata['message'])
            Log.Error(logprefix + msg)
            return ObjectContainer(header='Error', message=msg)
        elif jsondata['status'] == 2:
            msg = 'SSL required, check API url'
            Log.Error(logprefix + msg)
            return ObjectContainer(header='Error', message=msg)
        elif jsondata['status'] == 1:
            msg = 'Unknown error: ' + str(jsondata['message'])
            Log.Error(logprefix + msg)
            return ObjectContainer(header='Error', message=msg)
        elif jsondata['status'] == 0:
            msg = 'Credentials verified!'
            Log.Info(logprefix + msg)
            return ObjectContainer(header='Success', message=msg)
    else:
        msg = 'Missing status in JSON response'
        Log.Error(logprefix + msg)
        return ObjectContainer(header='Error', message=msg)
        
class SubInfo():
    def __init__(self, name, id, lang, ext, sub):
        self.name = name
        self.id = id
        self.lang = lang
        self.ext = ext
        self.sub = sub
        self.crc = Hash.CRC32(sub)

def Start():
    HTTP.CacheTime = 0
    HTTP.Headers['User-agent'] = OS_PLEX_USERAGENT
    Log("Start(): initialized")
    ValidatePrefs()

def BadFileName(filename):
    for word in badfilenames:
        if word.lower() in filename.lower():
            return True
    return False

# Prefs['username']
# Prefs['passkey']}

# Prepare a list of languages we want subs for
def GetLangPrefs(prefstype):
    langList = []
    if prefstype == 'hdbits':
        if(Prefs["langPref1"] != "None"):
            langList.append(langPrefs2HDbits[Prefs["langPref1"]])
        if(Prefs["langPref2"] != "None"):
            langList.append(langPrefs2HDbits[Prefs["langPref2"]])
        if(Prefs["langPref3"] != "None"):
            langList.append(langPrefs2HDbits[Prefs["langPref3"]])
    elif prefstype == 'plex':
        if(Prefs["langPref1"] != "None"):
            langList.append(langPrefs2Plex[Prefs["langPref1"]])
        if(Prefs["langPref2"] != "None"):
            langList.append(langPrefs2Plex[Prefs["langPref2"]])
        if(Prefs["langPref3"] != "None"):
            langList.append(langPrefs2Plex[Prefs["langPref3"]])
    elif prefstype == 'iso':
        if(Prefs["langPref1"] != "None"):
            langList.append(Prefs["langPref1"])
        if(Prefs["langPref2"] != "None"):
            langList.append(Prefs["langPref2"])
        if(Prefs["langPref3"] != "None"):
            langList.append(Prefs["langPref3"])
    return langList

def HdbLangToIso(lang):
    for key, value in langPrefs2HDbits.iteritems():
        if value == lang:
            return key
    return None

def PlexLangToIso(lang):
    for key, value in langPrefs2Plex.iteritems():
        if value == lang:
            return key
    return None

# Guess language from strings. first try values from langGuess dict, then try keys from langGuess dict,
# then try values from  langPrefs2Plex, then finally try values from langPrefs2Hdbits.
# These get progressively more inaccurate, may need to make this into an option for users.
# We also *only* guess the user prefered language(s) to decrease false positives
# Examples:
# guessLang("My.Little.Pony.de.srt") == "ger"; guessLang("My.Little.Pony.eng.srt") == "eng"
# guessLang("My.Little.Pony.Dutch.srt") == "dut"; guessLang("My.Little.Pony.uk.srt") == "eng"
# guessLang("My.English.Teacher.fr.srt") == "fre"
# False positives:
# guessLang("My.English.Teacher.srt") == "eng"
# guessLang("My.English.Teacher.blah.srt") == "eng"
def guessLang(string):
    searchstring = string.lower()
    langprefs = GetLangPrefs("iso")
    # short 2 letter country codes, e.g. "en", "nl", "sv"
    # These should only be matched when prefixed with special chars like . or _ or " " and suffixed with .
    # For example, "my.movie.en.srt" "my_movie_en.srt" "my movie en.srt"
    # No regex, this is way faster.
    for key, value in langPrefs2Plex.iteritems():
        if key in langprefs and ("." + value + "." in searchstring or "_" + value + "." in searchstring or " " + value + "." in searchstring):
            return key
    # hdbits country language prefs
    for key, value in langPrefs2HDbits.iteritems():
        if key in langprefs and ("." + value + "." in searchstring or "_" + value + "." in searchstring or " " + value + "." in searchstring):
            return key

    # full language name, e.g. "english" "dutch" "swedish" etc
    for key, value in langGuess.iteritems():
        if key in langprefs and value in searchstring:
            return key
    # custom short three letter language, e.g. "esp", "jap"
    for key, value in langGuessShort.iteritems():
        if key in langprefs and value in searchstring:
            return key
    # country code 3 letter language, e.g. "eng", "dut", "swe"
    for key, value in langGuess.iteritems():
        if key in langprefs and key in searchstring:
            return key
    return None

def matchEpisode(season, episode, filename):
    # sXX and eXX eg s01e09 or s01 e09 or s01.e09
    searchstring = filename.lower()
    if ("s" + str(season).zfill(2) in searchstring) and ("e" + str(episode).zfill(2) in searchstring):
        return True
     # XxXX eg 1x09
    elif (str(season) + "x" + str(episode).zfill(2) in searchstring):
        return True
    # season X episode X
    elif ("season " + str(season) + " episode " + str(episode) in searchstring):
        return True
    # .XXX. eg .109. - we need to check for dots otherwise we will match years and resolution
    elif ('.' + str(season) + str(episode).zfill(2) + '.' in searchstring):
        return True
    # _XXX_ eg _109_ - we need to check for underscores otherwise we will match years and resolution
    elif ("_" + str(season) + str(episode).zfill(2) + "_" in searchstring):
        return True
    else:
        return False

# guessSource returns:
# * WEB-DL | Blu-Ray | HDDVD | HDTV on a valid match
# * None on no match, or when sourcematching is disabled
# Subs for Blu-Ray and Remux will be considered the same.
# After some testing it appears that HDDVD and Blu-Ray timecodes are frequently off, so they are considered separately..
def guessSource(filename):
    if Prefs['SourceMatching'] == True:
        searchstring = filename.lower()
        if ("web-dl" in searchstring or "webdl" in searchstring):
            return "WEB-DL"
        elif ("blu-ray" in searchstring or "bluray" in searchstring or "remux" in searchstring):
            return "Blu-Ray"
        elif ("hddvd" in searchstring or "hd-dvd" in searchstring or "hd dvd" in searchstring):
            return "HDDVD"
        elif ("hdtv" in searchstring):
            return "HDTV"
        else:
            return None
    # Source matching disabled, simply always return None
    else:
        return None

def GetListOfTorrents(mediatype,mediaid,season = None,episode = None):
    if mediatype == "movie":
        logprefix = "GetListOfTorrents(" + str(mediatype) + "/" + str(mediaid) + "): "
    elif mediatype == "tv":
        logprefix = "GetListOfTorrents(" + str(mediatype) + "/" + str(mediaid) + "/s" + str(season).zfill(2) + "e" + str(episode).zfill(2) + "): "
    Log.Debug(logprefix + "called")
    apiurl = HDBITS_URL + "/api/torrents"
    # we are OK with include_dead, but we need to include only movie type with type_category=1 to avoid getting audo tracks etc
    if mediatype == "movie":
        queries = [{ "username": Prefs['username'], "passkey":Prefs['passkey'], "imdb": { "id": mediaid}, "include_dead":"true", "category": [ 1] }]
    # We do 2 queries for tv, one for the season packs (episode 0) and one for the specific episode
    elif mediatype == "tv":
        queries = [{ "username": Prefs['username'], "passkey":Prefs['passkey'], "tvdb": { "id": mediaid, "season": season, "episode":"0" }, "include_dead":"true" },
                { "username": Prefs['username'], "passkey":Prefs['passkey'], "tvdb": { "id": mediaid, "season": season, "episode": episode }, "include_dead":"true" }]
    result = []
    for query in queries:
        postdata = JSON.StringFromObject(query)
        try:
            response = HTTP.Request(apiurl, data=postdata, timeout=apitimeout,cacheTime=3600)
        except:
            Log.Exception(logprefix + "Unknown error while querying API")
            return None
        try:
            jsondata = JSON.ObjectFromString(response.content)
            # We append to the result in case we are doing 2 queries for tv
            result = result + jsondata["data"]
        except ValueError, e:
            Log.Exception(logprefix + "Incorrect response, aborting: " + str(e))
            return None
    Log.Debug(logprefix + "API returned " + str(len(result)) + " results")
    return result

def GetListOfSubs(torrent,mediatype, mediaid):
    logprefix = "GetListOfSubs(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent["id"]) + "): "
    Log.Debug(logprefix + "called, querying API")
    apiurl = HDBITS_URL + "/api/subtitles"
    # we only need to pass torrent_id
    query = {  "username": Prefs['username'], "passkey":Prefs['passkey'], "torrent_id": torrent["id"] }
    postdata = JSON.StringFromObject(query)
    try:
        response = HTTP.Request(apiurl, data=postdata, timeout=apitimeout,cacheTime=3600)
    except:
        Log.Exception(logprefix + "Unknown error while querying API")
        return None
    try:
        jsondata = JSON.ObjectFromString(response.content)
    except ValueError, e:
        Log.Exception(logprefix + "ValueError parsing results: " + str(e))
        return None
    # Count, log and pass results back as list
    result = jsondata["data"]
    Log.Debug(logprefix + "API returned " + str(len(result)) + " results")
    #pprint.pprint(subtitleresult)
    return result

def GetSub(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season = None, episode = None):
    if mediatype == "movie":
        logprefix = "GetSub(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "): "
    elif mediatype == "tv":
        logprefix = "GetSub(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "/s" + str(season).zfill(2) + "e" + str(episode).zfill(2) + "): "
    mediasource = guessSource(mediafilename)
    if mediasource == None:
        guessSource(mediadirname)
    dlUrl = HDBITS_URL + "/getdox.php?id=" + subtitle["id"] + "&passkey=" + Prefs['passkey']
    dlExt = string.split(subtitle["filename"], '.')[-1].lower() #Find suffix for this sub type
    Log.Debug(logprefix + "subtitle filename " + str(subtitle["filename"]) + ", download extension " + str(dlExt))
    subName = subtitle["filename"]
    subExt = dlExt
    if (mediatype == "tv") and (torrent["tvdb"]["episode"] == 0) and (matchEpisode(season,episode,subName) == False):
        Log.Debug(logprefix + "skipping: episode mismatch on " + str(subName) + " for season " + str(season) + " episode " + str(episode))
        return None
    else:
        if subtitle["language"] == "zz":
            isoLang = guessLang(subName)
            if isoLang == None:
                isoLang = guessLang(subtitle["title"])
        else:
            isoLang = HdbLangToIso(subtitle["language"])
        # Now map the ISO lang to Plex
        if isoLang == None:
            Log.Debug(logprefix + "no preferred language found for " + str(subName) + " (" + str(subtitle["title"]) + ")")
            return None
        else:
            subLang = langPrefs2Plex[isoLang] 
            # if we don't know our media source, or if it is disabled, accept anything
            # if we know our media source, match against sub name, sub filename, torrent filename or torrent name
            # often the torrent name is the accurate match. unfortunately we can't use the sites 'medium' ids due to the 'encode' class
            Log.Debug(logprefix + "SourceMatching: media name '" + str(mediadirname) + "/" + str(mediafilename) + "' = " + str(mediasource) + ", sub name '" + str(subName) + "' = " + str(guessSource(subName)) + ", sub filename '" + str(subtitle["filename"]) + "' = " + str(guessSource(subtitle["filename"])) + ", torrent filename '" + str(torrent["filename"]) + "' = " + str(guessSource(torrent["filename"])) + ", torrent name '" + str(torrent["name"]) + "' = " + str(guessSource(torrent["name"])))
            if ((mediasource == None) or (mediasource == guessSource(subName) or mediasource == guessSource(subtitle["filename"]) or mediasource == guessSource(torrent["filename"]) or mediasource == guessSource(torrent["name"]))):
                try:
                    # It is possible we already downloaded this subtitle. We use subtitle['id'] as key here
                    if not Data.Exists(subtitle["id"]):
                        # Download and store immediately
                        dl = HTTP.Request(dlUrl, timeout=apitimeout)
                        Data.Save(subtitle["id"],dl.content)
                    sub = Data.Load(subtitle["id"])
                    if(mediatype == "movie"):
                        Log.Debug(logprefix + "found: type=" + str(subExt) + ", language=" + str(subLang) + ", filename=" + str(subName) + ", mediasource=" + str(mediasource))
                    elif(mediatype == "tv"):
                        Log.Debug(logprefix + "found: type=" + str(subExt) + ", language=" + str(subLang) + ", season=" + str(season) + ", episode =" + str(episode) + ", filename=" + str(subName) + ", mediasource=" + str(mediasource))
                    return SubInfo(subName,subtitle['id'],subLang,subExt,sub)
                except:
                    Log.Exception(logprefix + "Unknown error while downloading")
                    return None
            else:
                Log.Debug(logprefix + "skipping: source mismatch for " + str(subName) + " against " + str(mediadirname) + "/" + str(mediafilename))
                return None

def GetSubArchive(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season = None, episode = None):
    if mediatype == "movie":
        logprefix = "GetSubArchive(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "): "
    elif mediatype == "tv":
        logprefix = "GetSubArchive(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "/s" + str(season).zfill(2) + "e" + str(episode).zfill(2) + "): "
    mediasource = guessSource(mediafilename)
    dlUrl = HDBITS_URL + "/getdox.php?id=" + subtitle["id"] + "&passkey=" + Prefs['passkey']
    dlExt = string.split(subtitle["filename"], '.')[-1].lower() #Find suffix for this sub type
    Log.Debug(logprefix + "subtitle filename " + str(subtitle["filename"]) + ", download extension " + str(dlExt))
    subName = subtitle["filename"]
    subExt = dlExt
    # zipped subtitle. Could be one, could be more
    # Due to the restrictions on sandboxed pythons, we will address the dowloaded files directly under DataItems
    try:
        if not Data.Exists(subtitle["id"]):
            # Download and store immediately
            dl = HTTP.Request(dlUrl, timeout=apitimeout)
            Data.Save(subtitle["id"],dl.content)
    except:
        Log.Exception(logprefix + "Unknown error while downloading")
        return None
    archivepath = os.getcwd() + '/DataItems/' + str(subtitle["id"])
    # sometimes people upload zips and name them .rar and vice versa, so we just try both.
    if zipfile.is_zipfile(archivepath):
        archive = zipfile.ZipFile(archivepath)
    elif rarfile.is_rarfile(archivepath):
        archive = rarfile.RarFile(archivepath)
    else:
        Log.Error(logprefix + "skipping: archive '" + str(subtitle["filename"]) + " is neither ZIP nor RAR")
        return None
    # Due to RPythons inability to allow __exit__ in rarfile.py, we can't use 'with' here :(
    try:
        # We need to be careful NOT to return inside this function - we need to just continue, build a list of subs, then return it AFTER parsing
        sublist = []
        for subName in archive.namelist():
            if BadFileName(subName):
                Log.Debug(logprefix + "skipping: bad file match on " + str(subName) + " in archive " + str(subtitle["filename"]) + " for season " + str(season) + " episode " + str(episode))
                continue
            subExt = string.split(subName, '.')[-1]
            if subExt in subtitleExt:
                # TODO: If somehow this single language archive has more than one file, we need to make some sort of educated guess as to what it is.
                #       But as long as plex does not have a way to specify additional info to the subtitle (Forced/SDH etc), we'll have to leave it as-is.
                if (mediatype == "tv") and (torrent["tvdb"]["episode"] == 0) and (matchEpisode(season,episode,subName) == False):
                    Log.Debug(logprefix + "skipping: episode mismatch on " + str(subName) + " in archive " + str(subtitle["filename"]) + " for season " + str(season) + " episode " + str(episode))
                    continue
                else:
                    if subtitle["language"] == "zz":
                        isoLang = guessLang(subName)
                        #if isoLang == None:
                            # this *is* a bad idea for multi language archives. don't do it.
                            #Log.Debug(logprefix + "guessing language from subtitle site title)")
                            #isoLang = guessLang(subtitle["title"])
                    else:
                        isoLang = HdbLangToIso(subtitle["language"])
                    if isoLang == None:
                        Log.Debug(logprefix + "no preferred language found for " + str(subName) + " (" + str(subtitle["title"]) + ") in archive " + str(subtitle["filename"]))
                        continue
                    else:
                        subLang = langPrefs2Plex[isoLang]
                        try:
                            # if we don't know our media source, accept anything
                            # if we know our media source, match movie metadata filename against subtitle file, subtitle archive filename, or torrent filename
                            Log.Debug(logprefix + "SourceMatching: media name '" + str(mediadirname) + "/" + str(mediafilename) + "' = " + str(mediasource) + ", sub name '" + str(subName) + "' = " + str(guessSource(subName)) + ", sub filename '" + str(subtitle["filename"]) + "' = " + str(guessSource(subtitle["filename"])) + ", torrent filename '" + str(torrent["filename"]) + "' = " + str(guessSource(torrent["filename"])) + ", torrent name '" + str(torrent["name"]) + "' = " + str(guessSource(torrent["name"])))
                            if ((mediasource == None) or (mediasource == guessSource(subName) or mediasource == guessSource(subtitle["filename"]) or mediasource == guessSource(torrent["filename"]) or mediasource == guessSource(torrent["name"]))):
                                sub = archive.read(subName)
                                if(mediatype == "movie"):
                                    Log.Debug(logprefix + "found: type=" + str(subExt) + ", language=" + str(subLang) + ", filename=" + str(subName) + ", archive=" + str(subtitle["filename"]) + ", mediasource=" + str(mediasource))
                                
                                elif (mediatype == "tv"):
                                    Log.Debug(logprefix + "found: type=" + str(subExt) + ", language=" + str(subLang) + ", season=" + str(season) + ", episode =" + str(episode) + ", filename=" + str(subName) + ", archive=" + str(subtitle["filename"]) + ", mediasource=" + str(mediasource))
                            
                                si = SubInfo(subName,subtitle['id'],subLang,subExt,sub)
                                sublist.append(si)
                            else:
                                Log.Debug(logprefix + "skipping: source mismatch for " + str(subName) + " against " + str(mediafilename) + "(inside archive " + str(subtitle["filename"]))
                                continue
                        except:
                            Log.Exception(logprefix + "failed to extract file " + str(subName) + " from archive " +  str(subtitle["filename"]))
                            continue
            else:
                Log.Debug(logprefix + "skipping: unsupported file " + str(subName) + " in archive " +  str(subtitle["filename"]))
                continue
        # We are done parsing, return sublist
        return sublist
    except:
        Log.Exception(logprefix + "Unknown archive error")
        return none
    finally:
        archive.close()



class HdbitsSubtitlesAgentMovies(Agent.Movies):
    name = 'HDBits.org Movie Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.imdb']
    
    def search(self, results, media, lang):
        logprefix = 'HdbitsSubtitlesAgentMovies(): '
        Log.Info(logprefix + "search called for imdb id %s" % media.primary_metadata.id.split('tt')[1].split('?')[0])
        results.Append(MetadataSearchResult(
          id    = media.primary_metadata.id.split('tt')[1].split('?')[0],
          score = 100
        ))
    
    
    def update(self, metadata, media, lang):
        mediaid = metadata.id
        mediatype = "movie"
        logprefix = "HdbitsSubtitlesAgentMovies(" + str(mediaid) + "): "
        Log.Debug(logprefix + "update called for mediaid " + str(mediaid))
        for item in media.items:
            for part in item.parts:
                mediafilename = os.path.basename(part.file)
                mediadirname = os.path.basename(os.path.dirname(part.file))
                torrents = GetListOfTorrents(mediatype,mediaid)
                tcount = 0
                sadded = 0
                spresent = 0
                sskipped = 0
                for torrent in torrents:
                    tcount = tcount + 1
                    subtitles = GetListOfSubs(torrent,mediatype,mediaid)
                    for subtitle in subtitles:
                        logprefix = "HdbitsSubtitlesAgentMovies(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "): "
                        extension = string.split(subtitle["filename"], '.')[-1].lower()
                        if (subtitle["language"] in GetLangPrefs("hdbits")):
                            if extension in subtitleExt:
                                si = GetSub(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid)
                                if si is not None:
                                    if not si.crc in part.subtitles[si.lang]:
                                        sadded = sadded + 1
                                        Log.Info(logprefix + "adding id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                        part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                    else:
                                        spresent = spresent + 1
                            elif (extension == 'rar') or (extension == 'zip'):
                                silist = GetSubArchive(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid)
                                for si in silist:
                                    if not si.crc in part.subtitles[si.lang]:
                                        sadded = sadded + 1
                                        Log.Info(logprefix + "adding id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                        part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                    else:
                                        spresent = spresent + 1
                            else:
                                sskipped = sskipped + 1
                                Log.Debug(logprefix + "skipping: unsupported subtitle format for file " + str(subtitle["filename"]))
                        elif (subtitle["language"] == "zz") and Prefs['MoviesOther'] == True:
                            if extension in subtitleExt:
                                si = GetSub(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid)
                                if si is not None:
                                    if not si.crc in part.subtitles[si.lang]:
                                        sadded = sadded + 1
                                        Log.Info(logprefix + "adding id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                        part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                    else:
                                        spresent = spresent + 1
                            elif (extension == 'rar') or (extension == 'zip'):
                                silist = GetSubArchive(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid)
                                for si in silist:
                                    if not si.crc in part.subtitles[si.lang]:
                                        sadded = sadded + 1
                                        Log.Info(logprefix + "adding id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                        part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                    else:
                                        spresent = spresent + 1
                            else:
                                sskipped = sskipped + 1
                                Log.Debug(logprefix + "skipping: unsupported subtitle format for file " + str(subtitle["filename"]))
                        else:
                            sskipped = sskipped + 1
                            Log.Debug(logprefix + "skipping: language preference mismatch on " +  str(subtitle["filename"]) + " (" + str(subtitle["language"]) + ")")
                logprefix = "HdbitsSubtitlesAgentMovies(" + str(mediaid) + "): "
                stotal = sadded + sskipped
                Log.Info(logprefix + str(stotal) + " subs found across " + str(tcount) + " torrents, " + str(sadded) + " matching subtitles added, " + str(spresent) + " matching subtitles already present, " + str(sskipped) + " non-matching subtitles skipped")


class HdbitsSubtitlesAgentTV(Agent.TV_Shows):
    name = 'HDBits.org TV Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.thetvdb']
    
    def search(self, results, media, lang):
        Log("TV SEARCH CALLED ON TVDB ID %s" % media.primary_metadata.id)
        results.Append(MetadataSearchResult(id = media.primary_metadata.id, score = 100))
    
    def update(self, metadata, media, lang):
        mediaid = metadata.id
        mediatype = "tv"
        logprefix = "HdbitsSubtitlesAgentTV(" + str(mediaid) + "): "
        Log.Debug(logprefix + "update called for mediaid " + str(mediaid))
        for season in media.seasons:
            for episode in media.seasons[season].episodes:
                for item in media.seasons[season].episodes[episode].items:
                    for part in item.parts:
                        mediafilename = os.path.basename(part.file)
                        mediadirname = os.path.basename(os.path.dirname(part.file))
                        torrents = GetListOfTorrents(mediatype,mediaid,season,episode)
                        tcount = 0
                        sadded = 0
                        spresent = 0
                        sskipped = 0
                        for torrent in torrents:
                            tcount = tcount + 1
                            subtitles = GetListOfSubs(torrent,mediatype,mediaid)
                            for subtitle in subtitles:
                                logprefix = "HdbitsSubtitlesAgentTV(" + str(mediatype) + "/" + str(mediaid) + "/" + str(torrent['id']) + '/' + str(subtitle['id']) + "/s" + str(season).zfill(2) + "e" + str(episode).zfill(2) + "): "
                                extension = string.split(subtitle["filename"], '.')[-1].lower()
                                if (subtitle["language"] in GetLangPrefs("hdbits")):
                                    if extension in subtitleExt:
                                        si = GetSub(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season, episode)
                                        if si is not None:
                                            if not si.crc in part.subtitles[si.lang]:
                                                sadded = sadded + 1
                                                Log.Info(logprefix + "adding: id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                                part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                            else:
                                                spresent = spresent + 1
                                    elif (extension == 'rar') or (extension == 'zip'):
                                        silist = GetSubArchive(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season, episode)
                                        for si in silist:
                                            if not si.crc in part.subtitles[si.lang]:
                                                sadded = sadded + 1
                                                Log.Info(logprefix + "adding: id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                                part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                            else:
                                                spresent = spresent + 1
                                    else:
                                        Log.Debug(logprefix + "skipping: unsupported subtitle format for file " + str(subtitle["filename"]))
                                        sskipped = sskipped + 1
                                elif (subtitle["language"] == "zz") and Prefs['MoviesOther'] == True:
                                    if extension in subtitleExt:
                                        si = GetSub(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season, episode)
                                        if si is not None:
                                            if not si.crc in part.subtitles[si.lang]:
                                                sadded = sadded + 1
                                                Log.Info(logprefix + "adding: id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                                part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                            else:
                                                spresent = spresent + 1
                                    elif (extension == 'rar') or (extension == 'zip'):
                                        silist = GetSubArchive(subtitle, torrent, mediafilename, mediadirname, mediatype, mediaid, season, episode)
                                        for si in silist:
                                            if not si.crc in part.subtitles[si.lang]:
                                                sadded = sadded + 1
                                                Log.Info(logprefix + "adding: id=" + str(si.id) + ", type=" + str(si.ext) + ", language=" + str(si.lang) + ", name=" + str(si.name))
                                                part.subtitles[si.lang][si.crc] = Proxy.Media(si.sub, ext=si.ext)
                                            else:
                                                spresent + spresent + 1
                                    else:
                                        Log.Debug(logprefix + "skipping: unsupported subtitle format for file " + str(subtitle["filename"]))
                                        sskipped = sskipped + 1
                                else:
                                    Log.Debug(logprefix + "skipping: language preference mismatch on " +  str(subtitle["filename"]) + " (" + str(subtitle["language"]) + ")")
                        logprefix = "HdbitsSubtitlesAgentTV(" + str(mediaid) + "): "
                        stotal = sadded + sskipped
                        Log.Info(logprefix + str(stotal) + " subs found across " + str(tcount) + " torrents, " + str(sadded) + " matching subtitles added, " + str(spresent) + " matching subtitles already present, " + str(sskipped) + " non-matching subtitles skipped")
    
    
    
#                        Log("Found %d subs" % len(subsList))
#                        for si in subsList:
#                            part.subtitles[si.lang][si.url] = Proxy.Media(si.sub, ext=si.ext)


# From https://github.com/MrHistamine/Caster/blob/master/Caster.bundle/Contents/Code/__init__.py
####################################################################################################
#   Write the passed-in string to the specified file, at the specified address.
#       destPath - the full path to the directory where the file will be written
#       fullFileName - the full name of the file (including the extension)
#       fileContents - the string to write to the file
#
def WriteFile(destPath, fullFileName, fileContents):
    fileAddress = os.path.join(destPath, fullFileName)
    fd = os.open(fileAddress, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
    outFile = os.fdopen(fd, "w+")
    outFile.write(fileContents)
    outFile.close()
    Log.Debug('The file: \"' + fileAddress + '\", was successfully written to.')
