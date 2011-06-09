#hdbits.org

import string, os

HDBITS_MAIN = "https://hdbits.org/"
HDBITS_SEARCH_PAGE = "https://hdbits.org/dox.php?%s=1&search=%s"
HDBITS_LOGIN_PAGE = 'https://hdbits.org/login.php'
HDBITS_LOGON_PAGE = 'https://hdbits.org/takelogon.php'
OS_PLEX_USERAGENT = 'plexapp.com v9.0'
subtitleExt       = ['utf','utf8','utf-8','sub','srt','smi','rt','ssa','aqt','jss','ass','idx']

langPrefs2HDbits = {'eng':'uk', 'swe':'se'}
#Find these in the DefaultPrefs.json and http://dev.plexapp.com/docs/api/localekit.html#locale-language
langPrefs2Plex = {'eng':'en', 'swe':'sv'}

def Start():
    HTTP.CacheTime = 10000
    HTTP.Headers['User-agent'] = OS_PLEX_USERAGENT
    Log("START CALLED")

def checkLogin():
    Log("checkLogin")
#TODO: Instead of trusting the server to redirect us to the login page if we're not logged in. Check for the cookie
    #instead with HTTP.GetCookiesForURL(url)?

    elem = HTML.ElementFromURL(HDBITS_MAIN)
    lols = elem.xpath("//form//input[@name='lol']/@value")
    Log("lols %s" % lols)

    if len(lols) == 1:
        lol = str(lols[0])
        values = {'uname':Prefs['username'],'password':Prefs['password'],'lol':lol}
        elem2 = HTML.ElementFromURL(HDBITS_LOGON_PAGE, values=values)
        svar1 = HTML.StringFromElement(elem2)

#Prepare a list of languages we want subs for
def getLangList():
    langList = [Prefs["langPref1"]]
    if(Prefs["langPref2"] != "None"):
        langList.append(Prefs["langPref2"])

    return langList


#Do a basic search for the filename and return all sub urls found
def simpleSearch(fileName, lang = 'eng'):
#First make sure we are logged in
    checkLogin() 

#Prepare the filename for search by removing the suffix and other nuisances
    lastDotIndex = string.rfind(fileName, '.')
    if(lastDotIndex > -1):
        fileName = fileName[0:lastDotIndex]

    fileName = string.replace(fileName, '.', ' ')
    fileName = string.replace(fileName, '(',' ')
    fileName = string.replace(fileName, ')',' ')
    fileName = string.replace(fileName, '-',' ')
    Log("Searching for: %s" % fileName)

    urlName = String.Quote(fileName, usePlus=True)
    Log("escaped file name: %s" % urlName)
    searchUrl = HDBITS_SEARCH_PAGE % (langPrefs2HDbits[lang], urlName)
    Log("searchUrl: %s" % searchUrl)
    elem = HTML.ElementFromURL(searchUrl)
    #Log("Search page: %s" % HTML.StringFromElement(elem))

#Find all sub urls on this page and return the link/url to them
    subtitles = elem.xpath("//a[starts-with(@href,'getdox.php')]/@href")
    for subtitle in subtitles:
        Log("Subtitle: %s" % subtitle)

    return subtitles

class SubInfo():
    lang = None
    url = None
    sub = None
    subExt = None

def getSubsForPart(part):
    fileName = os.path.basename(part.file)
    Log("Filename: %s" % fileName)
#For each language defined in preferences, do a search
    subsList = []
    for lang in getLangList():
        plexLang = Locale.Language.Match(langPrefs2Plex[lang])
        Log("LangTest: %s" % plexLang)
        subtitleUrls = simpleSearch(fileName, lang)
#For each sub found. Fetch it and hand it over to Plex with the right language and suffix set
        for url in subtitleUrls:
            splitUrl = string.split(url, '/')
            splitUrl[-1] = String.Quote(splitUrl[-1], usePlus=True)
            url = string.join(splitUrl, '/')
            subUrl = HDBITS_MAIN + url
            subExt = string.split(url, '.')[-1] #Find suffix for this sub type
            Log("SubUrl: %s" % subUrl)
            Log("SubExt: %s" % subExt)
            if subExt in subtitleExt:
                Log("subExt %s is ok" % subExt)
                sub = HTTP.Request(subUrl, immediate=True).content
                si = SubInfo()
                si.lang = plexLang
                si.url = url
                si.sub = sub
                si.subExt = subExt
                subsList.append(si)
            else:
                Log("Can't handle sub of type: %s" % subExt)
    return subsList

class HdbitsSubtitlesAgentMovies(Agent.Movies):
    name = 'HDBits.org Subtitles Movies'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.imdb']

    def search(self, results, media, lang):
        Log("MOVIE SEARCH CALLED")    
        results.Append(MetadataSearchResult(id = 'null', score = 100))

    def update(self, metadata, media, lang):
            Log("MOVIE UPDATE CALLED")
            for item in media.items:
                for part in item.parts:
                    subsList = getSubsForPart(part)
                    valid_names = list()
                    for si in subsList:
                        part.subtitles[si.lang][si.url] = Proxy.Media(si.sub, ext=si.subExt)
                        valid_names.append(si.lang)
                        part.subtitles[si.lang].validate_keys(valid_names)
                        Log("Validating keys...")

class HdbitsSubtitlesAgentMovies(Agent.TV_Shows):
    name = 'HDBits.org TV Subtitles'
    languages = [Locale.Language.English]
    primary_provider = False
    contributes_to = ['com.plexapp.agents.thetvdb']

    def search(self, results, media, lang):
        Log("TV SEARCH CALLED")    
        results.Append(MetadataSearchResult(id = 'null', score = 100))

    def update(self, metadata, media, lang):
        Log("TvUpdate. Lang %s" % lang)
        Log("media: %s" % media)
        for season in media.seasons:
            for episode in media.seasons[season].episodes:
                for item in media.seasons[season].episodes[episode].items:
                    for part in item.parts:
                        subsList = getSubsForPart(part)
                        Log("Found %d subs" % len(subsList))
                        valid_names = list()
                        for si in subsList:
                            part.subtitles[si.lang][si.url] = Proxy.Media(si.sub, ext=si.subExt)
                            valid_names.append(si.url)
                            Log("Validating keys...")
                            part.subtitles[si.lang].validate_keys(valid_names)
