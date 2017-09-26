from pymongo import *
import exceptions
import traceback
from prov.model import ProvDocument, Namespace, Literal, PROV, Identifier
import datetime
import dateutil.parser
import uuid
import traceback
import os
import socket
import json
import httplib, urllib
import csv
import StringIO
from urlparse import urlparse
from itertools import chain
import sys

def makeHashableList(listobj,field):
     listobj=[x[field] for x in listobj]
     return listobj

def clean_empty(d):
    if not isinstance(d, (dict, list)):
        return d
    if isinstance(d, list):
        return [v for v in (clean_empty(v) for v in d) if v]
    return {k: v for k, v in ((k, clean_empty(v)) for k, v in d.items()) if v}

  

def formatArtifactDic(dic):
 for x in dic:
     if type(dic[x])==list:
         dic[x]=str(dic[x])
 return dic
     

def resolveMissingTerms(trace):
    if "iterationId" not in trace:
            trace["iterationId"]=trace["instanceId"]
    if "worker" not in trace:
            trace["worker"]="NaN"
    if "actedOnBehalfOf" not in trace:
            trace["actedOnBehalfOf"]=trace["name"]
    return trace
     
     
def toW3Cprov(ling,bundl,format='xml'):
        entities={}
        g = ProvDocument()
        vc = Namespace("s-prov", "http://s-prov/ns/#")  # namespaces do not need to be explicitly added to a document
        knmi = Namespace("knmi", "http://knmi.nl/ns/#")
        provone = Namespace("provone", "http://vcvcomputing.com/provone/provone.owl#")
        con = Namespace("con", "http://verce.eu/control")
        g.add_namespace("dcterms", "http://purl.org/dc/terms/")
        g.add_namespace("vcard", "http://www.w3.org/2006/vcard/ns")
        
        'specify bundle'
        bundle=None
        for trace in bundl:
            'specifing user'
            
            ag=g.agent(knmi[trace["username"]],other_attributes={"prov:type":"prov:Person", "vcard:uuid":trace["username"]})  # first time the ex namespace was used, it is added to the document automatically
            
            if 'ns' in trace:
                for x in trace['ns']:
                    g.add_namespace(x,trace['ns'][x])

           

                
            if trace['type']=='workflow_run':
                
                trace.update({'runId':trace['_id']})
                bundle=g.bundle(knmi["Bundle_"+trace["runId"]])
                bundle.wasAttributedTo(knmi[trace["runId"]], ag)
                
                dic={}
                i=0
                
                for key in trace:
                    
                
                    if key != "input":
                        if ':' in key:
                            dic.update({key: trace[key]})
                        
                        if key == "modules" or key == "source":
                                continue
                        
                        elif key == "tags":
                            dic.update({vc[key]: str(trace[key])})
                        #else:
                        #    dic.update({knmi[key]: trace[key]})
                dic.update({'prov:type': vc['WFExecution']})
                WFE=bundle.activity(knmi[trace["runId"]], None, None, dic)
                
                dic={}
                i=0

                if 'source' in trace:
                    wfp = bundle.entity(knmi["WF_"+trace["_id"]+"_"+str(i)], other_attributes={'prov:type':'provone:Workflow'})
                    for y in trace['source']:
                        dic={'prov:type': vc['Implementation'],
                             's-prov:source':"github://",
                             's-prov:type':trace['source'][y]['type'],
                             's-prov:functionName':trace['source'][y]['functionName'] if 'functionName' in trace['source'][y] else None
                             }

                        dic=clean_empty(dic)                                                             
                        imp=bundle.entity(knmi["Imp_"+trace["_id"]+"_"+str(i)], other_attributes=dic)
                        bundle.hadMember(wfp,imp)
                        i=i+1
                    bundle.wasAssociatedWith(WFE,wfp)
                 
                if type(trace['input'])!=list:
                    trace['input']=[trace['input']]

                wp = bundle.collection(knmi["WFPar_"+trace["_id"]], other_attributes={'prov:type': vc['WFExecutionParameter']} )
                for y in trace['input']:
                    dic.update({'prov:type': vc['Data']})
                    for key in y:
                        if ':' in key:
                            dic.update({key: y[key]})
                        else:
                            dic.update({vc[key]: y[key]})
                    

                    dt = bundle.collection(knmi[trace["_id"]+"_"+str(i)], formatArtifactDic(dic))
                    bundle.hadMember(wp,dt)
                    i=i+1
                    
                bundle.used(knmi[trace["runId"]], wp)
                    
                    
        'specify lineage'
        for trace in ling:
            trace = resolveMissingTerms(trace)
            
           
            'specifing creator of the activity (to be collected from the registy)'
        
            if 'creator' in trace:
                bundle.agent(knmi["ag_"+trace["creator"]],other_attributes={"dcterms:creator":trace["creator"]})  # first time the ex namespace was used, it is added to the document automatically
                bundle.wasAttributedTo(knmi[trace["runId"]], knmi["ag_"+trace["creator"]])
                
            'adding activity information for lineage'
            dic={}
            for key in trace:
                
                if type(trace[key])!=list:
                    if ':' in key:
                        dic.update({key: trace[key]})
                    else:
                        
                        if key=='location':
                            
                            dic.update({"prov:location": trace[key]})    
                        else:
                            dic.update({knmi[key]: trace[key]})
            
            
                
            if "Invocation_"+trace["iterationId"] not in entities:
                ac=bundle.activity(knmi["Invocation_"+trace["iterationId"]], trace["startTime"], trace["endTime"], other_attributes=dic.update({'prov:type': vc["Invocation"]}))
                entities["Invocation_"+trace["iterationId"]]=ac
                bundle.wasAssociatedWith(ac,knmi["ComponentInstance_"+trace["instanceId"]])
            else:
                ac=entities["Invocation_"+trace["iterationId"]]
                if (ac.get_endTime()<dateutil.parser.parse(trace["endTime"])):
                   ac=entities["Invocation_"+trace["iterationId"]]
                   ac.set_time(ac.get_startTime(), trace["endTime"])
            
            
            if "ComponentInstance_"+trace["instanceId"] not in entities:
                ag=bundle.agent(knmi["ComponentInstance_"+trace["instanceId"]], other_attributes={"prov:type":vc["ComponentInstance"],vc["worker"]:trace['worker'],vc["pid"]:trace['pid']})
                entities["ComponentInstance_"+trace["instanceId"]]=1
                bundle.actedOnBehalfOf(knmi["ComponentInstance_"+trace["instanceId"]],knmi["Component_"+trace["actedOnBehalfOf"]+"_"+trace["runId"]])
                
            
            
            if "Component_"+trace["actedOnBehalfOf"]+"_"+trace["runId"] not in entities:
                ag=bundle.agent(knmi["Component_"+trace["actedOnBehalfOf"]+"_"+trace["runId"]], other_attributes={"prov:type":vc["Component"],"s-prov:functionName":trace["name"]})
                entities["Component_"+trace["actedOnBehalfOf"]+"_"+trace["runId"]]=1
                bundle.wasAssociatedWith(WFE,knmi["Component_"+trace["actedOnBehalfOf"]+"_"+trace["runId"]])
                
              
               
            'adding parameters to the document as input entities'
            dic={}
            for x in trace["parameters"]:
                if ':' in x["key"]:
                    dic.update({x["key"]: x["val"]})
                else:
                    dic.update({knmi[x["key"]]: x["val"]})
                
            dic.update({'prov:type':vc['ComponentParameters']})
            
            
            bundle.entity(knmi["CPar_"+trace["instanceId"]], formatArtifactDic(dic))
            bundle.used(knmi['Invocation_'+trace["iterationId"]], knmi["CPar_"+trace["instanceId"]], identifier=knmi["used_"+trace["iterationId"]])

            'adding input dependencies to the document as input entities'
            dic={}
        
            for x in trace["derivationIds"]:
                'state could be added'   
            #dic.update({'prov:type':'parameters'})
            
                if 'DerivedFromDatasetID' in x and x['DerivedFromDatasetID']:
                
                    #if "Data_"+x["DerivedFromDatasetID"] not in entities:
                    #    c1=bundle.collection(knmi["Data_"+x["DerivedFromDatasetID"]])
                    #    entities["Data_"+x["DerivedFromDatasetID"]]=c1
                    #    print "USED"
                    #else:
                    #    print "EXisTS"
                    #    c1=entities["Data_"+x["DerivedFromDatasetID"]] 
                           
                    bundle.used(knmi['Invocation_'+trace["iterationId"]], knmi["Data_"+x["DerivedFromDatasetID"]], identifier=knmi["used_"+trace["iterationId"]+"_"+x["DerivedFromDatasetID"]])



            'adding entities to the document as output metadata'
            for x in trace["streams"]:
                i=0
                state=None
                parent_dic={}
                for key in x:
                        if key=='con:immediateAccess':
                            
                            parent_dic.update({knmi['immediateAccess']: x[key]}) 
                        elif key=='location':
                            parent_dic.update({"prov:location": str(x[key])})
                        elif key=='port':
                            parent_dic.update({provone["outPort"]: str(x[key])})
                        elif key == 'content':
                            None
                        else:
                            parent_dic.update({vc[key]: str(x[key])})
                

                parent_dic.update({'prov:type':vc['Data']})           
                 
            
                
                #if "Data_"+x["id"] not in entities:
                if knmi["Data_"+x["id"]] not in entities:
                    c1=bundle.collection(knmi["Data_"+x["id"]],other_attributes=parent_dic)
                    entities[knmi["Data_"+x["id"]]]=1

                 
                    
                    bundle.wasGeneratedBy(knmi["Data_"+x["id"]], knmi["Invocation_"+trace["iterationId"]], identifier=knmi["wgb_"+x["id"]])
                
                    if 'port' in x and (x['port']=='state' or x['port']=='_d4p_state'):
                        state=bundle.collection(knmi["StateCollection_"+trace["instanceId"]])
                        bundle.hadMember(state,c1)

                    if state!=None:
                        bundle.wasAttributedTo(state,knmi["Invocation_"+trace["iterationId"]])



                    dd=0
                    for d in trace['derivationIds']:
                        if 'DerivedFromDatasetID' in x and x['DerivedFromDatasetID']:
                            bundle.wasDerivedFrom(knmi["Data_"+x["id"]], knmi["Data_"+d['DerivedFromDatasetID']],identifier=knmi["wdf_"+x["id"]+"_"+d['DerivedFromDatasetID']])
                            dd+=1
                
                    for y in x["content"]:
                
                        dic={}
                
                        if isinstance(y, dict):
                            val=None
                            for key in y:
                        
                                try: 
                                    val =num(y[key])
                                
                                except Exception,e:
                                    val =str(y[key])
                            
                                if ':' in key:
                                    dic.update({key: val})
                                else:
                                    dic.update({knmi[key]: val})
                        else:
                            dic={knmi['text']:y}
                    
                        dic.update({'prov:type':vc['DataGranule']})
                 
                    #dic.update({"verce:parent_entity": vc["data_"+x["id"]]})
                    
                        e1=bundle.entity(knmi["DataGranule_"+x["id"]+"_"+str(i)], dic)
                    
                         
                        bundle.hadMember(knmi["Data_"+x["id"]], knmi["DataGranule_"+x["id"]+"_"+str(i)])
                    
                    i=i+1

        if format =='w3c-prov-json':
            return str(g.serialize(format='json'))
        elif format=='png':
            output = StringIO.StringIO()
            g.plot('test.png')
            return output
        else:
            return g.serialize(format=format)

class ProvenanceStore(object):

    def __init__(self, url):
 
        self.conection = MongoClient(url, 27017)
        #db = self.conection["verce-prov"]
        #self.lineage = db['lineage']
        #workflow = db['workflow']
        
        'too specific here, have to be migrated to gateway-api'
        #self.solver = db['solver']
        
    'extract information about a list of workflow runs starting from start to limit'    
    
#suport for rest call on workflow resources 
    def getWorkflows(self,**kwargs):
        #db = self.conection["verce-prov"]
        try:
            keylist=None
            maxvaluelist=None
            minvaluelist=None
            if 'idlist' in kwargs:
                memory_file = StringIO.StringIO(kwargs['idlist'][0])
                idlist = csv.reader(memory_file).next()
                
                return self.getUserRunbyIds(kwargs['username'][0],idlist,**kwargs)
            else:
               try:
                    memory_file = StringIO.StringIO(kwargs['keys'][0]) if 'keys' in kwargs else None
                    keylist = csv.reader(memory_file).next() 
                    memory_file = StringIO.StringIO(kwargs['maxvalues'][0]); 
                    maxvaluelist = csv.reader(memory_file).next()
                    memory_file2 = StringIO.StringIO(kwargs['minvalues'][0]);
                    minvaluelist = csv.reader(memory_file2).next()
               except:
                    None;
                 #return {'success':False, 'error':'Invalid Query Parameters'}
               
               return self.getUserRunsValuesRange(kwargs['username'][0],keylist,maxvaluelist,minvaluelist,**kwargs)
  
        except Exception:
            traceback.print_exc()
            raise 
        #self.getUserRuns(kwargs['username'][0],**kwargs)
        
#suport for rest call on entities resources         
    def getEntities(self,**kwargs):
        keylist=None
        maxvaluelist=None
        minvaluelist=None
        vluelist=None
        try:
            memory_file = StringIO.StringIO(kwargs['keys'][0]) if 'keys' in kwargs else None
            keylist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(kwargs['maxvalues'][0]);
            maxvaluelist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(kwargs['minvalues'][0]);
            minvaluelist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(request.args['values'][0]) if 'values' in kwargs else None
            vluelist = csv.reader(memory_file).next() if memory_file != None else None
            
            return self.getEntitiesBy(kwargs['method'][0],keylist,maxvaluelist,minvaluelist,vluelist,**kwargs)
  
        except Exception:
             
            traceback.print_exc()
            return self.getEntitiesBy(kwargs['method'][0],keylist,maxvaluelist,minvaluelist,vluelist,**kwargs)
            
        
    def makeElementsSearchDic(self,keylist,mnvaluelist,mxvaluelist):
        elementsDict={}
        
        for x in keylist:
            maxval=mxvaluelist.pop(0)
            minval=mnvaluelist.pop(0)
            try: 
                maxval =self.num(maxval)
                minval =self.num(minval)
            except Exception,e:
                None

                
            elementsDict.update({x:{"$lte":maxval,"$gte":minval }})
        
        searchDic={'streams.content':{'$elemMatch':elementsDict}}
        return searchDic
    
    def getEntitiesFilter(self,searchDic,keylist,mxvaluelist,mnvaluelist,start,limit):
            elementsDict ={}
            searchContextDic={}
            db = self.conection["verce-prov"]
            lineage = db['lineage']
            #if iterationId!=None:
            
            if keylist==None:
                print "Filter Query: "+str(searchDic)
                obj = lineage.find(searchDic,{"runId":1,"streams":1,"parameters":1,'startTime':1,'endTime':1,'errors':1,'derivationIds':1,'iterationId':1}).sort("endTime",direction=-1)[start:start+limit]
                totalCount = lineage.count(searchDic)
                #lineage.count(searchDic)
                return (obj,totalCount)
            else:
                
                for x in keylist:
                    
                    maxval=mxvaluelist.pop(0)
                    minval=mnvaluelist.pop(0)
                    try: 
                        maxval =self.num(maxval)
                        minval =self.num(minval)
                    except Exception,e:
                        None

                
                    elementsDict.update({x:{"$lte":maxval,"$gte":minval }})
                    searchContextDic={'streams.content':{'$elemMatch':elementsDict}}
                    
                    searchDic.update(searchContextDic)
                    
                    
                 
                print "Filter Query: "+str(searchContextDic)
                #obj =  lineage.find(activ_searchDic,{"runId":1,"streams.content.$":1,'endTime':1,'errors':1,"parameters":1})[start:start+limit].sort("endTime",direction=-1)
                obj= lineage.aggregate(pipeline=[{'$match':searchContextDic},
                                                    {"$unwind": "$streams" },
                                                    #{ "$unwind": "$streams.content" },
                                                    
                                                    {'$group':{'_id':'$_id', 'derivationIds':{ '$first': '$derivationIds' },'parameters': { '$first': '$parameters' },'runId': { '$first': '$runId' },'endTime': { '$first': '$endTime' },'startTime': { '$first': '$startTime' },'errors': { '$first': '$errors' },'streams':{ '$push':{'content' :'$streams.content','format':'$streams.format','location':'$streams.location','id':'$streams.id'}}}},
                                                    
                                                    ]) 
                return obj#totalCount=totalCount+lineage.find(activ_searchDic,{"runId":1}).count()
                    
            
            
            
            
    
    
    
    
    def exportDataProvenance(self, id,**kwargs):
        
        
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        lineage = db['lineage']
        totalCount=lineage.find({'runId':id}).count()
        
        tracelist=[]
        if 'all' in kwargs and kwargs['all'][0].upper()=='TRUE':
             
            self.getTraceList(id, 1000,tracelist) 
        elif 'level' in kwargs:  
            self.getTraceList(id, self.num(kwargs['level'][0]),tracelist) 
            
              #lineage.find({'runId':id}).sort("endTime",direction=-1)
            
        bundle=workflow.find({"_id":tracelist[0]['runId']}).sort("startTime",direction=-1)
        
        if 'format' in kwargs:
            return toW3Cprov(tracelist,bundle,format = kwargs['format'][0]),0
        else:
            return toW3Cprov(tracelist,bundle),0
            
            
    
    
    def exportRunProvenance(self, id,**kwargs):
        
        
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        lineage = db['lineage']
        totalCount=lineage.find({'runId':id}).count()
        cursorsList=list()
        
        if 'all' in kwargs and kwargs['all'][0].upper()=='TRUE':
            
            lineage=lineage.find({'runId':id}).sort("endTime",direction=-1)
             
            bundle=workflow.find({"_id":id}).sort("startTime",direction=-1)
            
            if 'format' in kwargs:
                return toW3Cprov(lineage,bundle,format = kwargs['format'][0]),0
            else:
                return toW3Cprov(lineage,bundle),0
            
                    
                    
        output = {"w3c-prov":exportDocList};
        output.update({"totalCount": totalCount})
      
        return  (output,totalCount)
    
    def exportAllRunProvenance(self, id,**kwargs):
        
        
        
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        totalCount=lineage.find({'runId':id}).count()+1
        cursorsList=list()
        
        if ('start' in kwargs and int(kwargs['start'][0])==0):
            cursorsList.append(workflow.find({"_id":id}))
        
        
        if 'all' in kwargs and kwargs['all'][0].upper()=='TRUE':
            
            cursorsList.append(lineage.find({'runId':id})[int(kwargs['start'][0]):int(kwargs['start'][0])+int(kwargs['limit'][0])].sort("endTime",direction=-1))
             
        else:
            cursorsList.append(lineage.find({'runId':id})[int(kwargs['start'][0]):int(kwargs['start'][0])+int(kwargs['limit'][0])].sort("endTime",direction=-1))

        exportDocList = list()
        
        
        
        
        
        for cursor in cursorsList:    
            for x in cursor:
                if 'format' not in kwargs or kwargs['format'][0].find('w3c-prov')!=-1:
                    
                    exportDocList.app(x,format = kwargs['format'][0] if 'format' in kwargs else 'w3c-prov-json')
        
        output = exportDocList
        
      
        return  (output,totalCount)
    
    def getSolverConf(self,path,request):
        db = self.conection["verce-prov"]
        solver = db['solver']
        try:
            solver = solver.find_one({"_id":path})
            if (solver!=None):
                solver.update({"success":True})
                userId = request.args["userId"][0] if "userId" in request.args else False
                def userFilter(item): return (not "users" in item) or (userId and userId in item["users"])
                def velmodFilter(item):
                    item["velmod"] = filter(userFilter, item["velmod"])
                    return item
                solver["meshes"] = map(velmodFilter, filter(userFilter, solver["meshes"]))
                return solver
            else:
                return {"success":False, "error":"Solver "+path+" not Found"}
            
        except Exception, e:
            return {"success":False, "error":str(e)}
    
    
    
    def getUserRunbyIds(self,userid,id_list,**kwargs):
        
         
        runids=[]
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        obj=workflow.find({"_id":{"$in":id_list},'username':userid},{"startTime":-1,"system_id":1,"description":1,"name":1,"workflowName":1,"grid":1,"resourceType":1,"resource":1,"queue":1}).sort("startTime",direction=-1)
        totalCount=workflow.find({"_id":{"$in":id_list}}).sort("startTime",direction=-1).count()
        for x in obj:
            
            runids.append(x)
        
            
        output = {"runIds":runids};
        output.update({"totalCount": totalCount})
        
        return output
    
    
    def getUserRunsValuesRange(self,userid,keylist,maxvaluelist,minvaluelist,**kwargs):
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        lineage = db['lineage']
        elementsDict ={}
        output=None
        runids=[]
        uniques=None
        totalCount=0
        start=int(kwargs['start'][0])
        limit=int(kwargs['limit'][0])
        if keylist==None: 
            keylist=[]
        
        if ((keylist==None or len(keylist)==0) and 'activities' not in kwargs):
            return self.getUserRuns(userid, **kwargs)
        
        if 'activities' in kwargs:
             
            values=str(kwargs['activities'][0]).split(',')
            intersect=False
            
            for y in values:
                 
                #curs=lineage.find({'username':userid,'name':y})
                 
                uniques_act=lineage.aggregate(pipeline=[{'$match':{'username':userid,'name':y}},
                                                    {'$group':{'_id':'$runId','startTime':{ '$first': '$startTime' }}},
                                                    {'$sort':{'startTime':-1}},
                                                    {'$project':{'_id':1}}]) 
                
                 
                uniques_act=makeHashableList(uniques_act,'_id')
                
                if intersect==True:
                    uniques=list(set(uniques).intersection(set(uniques_act)))
                else:
                    uniques=uniques_act
                    intersect=True
                
         
         
        if len(keylist)!=0 and "mime-type" in keylist:
            values=list((set(minvaluelist).union(set(maxvaluelist))))
            #totalCount=totalCount+len(lineage.find({'username':userid,'streams.format':{'$in':values}}).distinct("runId"))
            uniques_mime=lineage.aggregate(pipeline=[{'$match':{'username':userid,'streams.format':{'$in':values}}},
                                                    {'$group':{'_id':'$runId','startTime':{ '$first': '$startTime' }}},
                                                    {'$sort':{'startTime':-1}},
                                                    {'$project':{'_id':1}}
                                                    ]) 
            
            #lineage.find({'username':userid,'streams.format':{'$in':values}}).distinct("runId")
            uniques_mime=makeHashableList(uniques_mime,'_id')

            i = keylist.index('mime-type')
            minvaluelist.pop(i)
            maxvaluelist.pop(i)
            keylist.remove('mime-type')
            
            if uniques!=None:
                uniques=list(set(uniques).intersection(set(uniques_mime)))
            else:
                uniques=uniques_mime
        
        
        for x in keylist:
            maxval=maxvaluelist.pop(0)
            minval=minvaluelist.pop(0)
            try: 
                maxval =self.num(maxval)
                minval =self.num(minval)
            except Exception,e:
                None
            
            objdata=lineage.aggregate(pipeline=[{'$match':{'username':userid,'streams.content':{'$elemMatch':{x:{"$lte":maxval,"$gte":minval }}}}},
                                                    {'$group':{'_id':'$runId','startTime':{ '$first': '$startTime' }}},
                                                    {'$sort':{'startTime':-1}},
                                                    {'$project':{'_id':1}}
                                                    ]) 
            objdata=makeHashableList(objdata,'_id')
            #lineage.find({'username':userid,'streams.content':{'$elemMatch':{x:{"$lte":maxval,"$gte":minval }}}},{"startTime":-1,'runId':1}).sort("startTime",direction=-1).distinct("runId") 
            objpar=lineage.aggregate(pipeline=[{'$match':{'username':userid,'parameters':{'$elemMatch':{'key':x,'val':{"$lte":maxval,"$gte":minval }}}}},
                                                    {'$group':{'_id':'$runId','startTime':{ '$first': '$startTime' }}},
                                                    {'$sort':{'startTime':-1}},
                                                    {'$project':{'_id':1}}
                                                    ]) 
            objpar=makeHashableList(objpar,'_id')
            #lineage.find({'username':userid,'parameters':{'$elemMatch':{'key':x,'val':{"$lte":maxval,"$gte":minval }}}},{"startTime":-1,'runId':1}).sort("startTime",direction=-1).distinct("runId")           
              
            object_union=list(set(objdata).union(set(objpar)))
            
             
            
            if uniques!=None:
                 
                uniques=list(set(uniques).intersection(set(object_union)))
                 
            else:
                uniques=object_union
                
      
       
        totalCount=len(uniques)
        
        #uniques=[x['_id'] for x in uniques]
        
        obj=workflow.find({"_id":{"$in":uniques[start:start+limit]}},{"startTime":-1,"system_id":1,"description":1,"name":1,"workflowName":1,"grid":1,"resourceType":1,"resource":1,"queue":1}).sort("startTime",direction=-1)
         
        for x in obj:
            
            runids.append(x)
        
            
        output = {"runIds":runids};
        output.update({"totalCount": totalCount})
        return output
    
    
    def getEntitiesByValuesRange(self,path,keylist,mtype,start,limit,runId=None,iterationId=None,dataId=None,maxvaluelist=None,minvaluelist=None,valuelist=None):
         
        elementsDict ={}
        output=None
        runids=[]
        uniques=None
       
        for x in keylist:
            maxval=maxvaluelist.pop(0)
            minval=minvaluelist.pop(0)
            try: 
                maxval =self.num(maxval)
                minval =self.num(minval)
            except Exception,e:
                None
             
            if runId!=None:
                
                objdata=lineage.find({'runId':runId,'streams.format':mtype,'streams.content':{'$elemMatch':{x:{"$lte":maxval,"$gte":minval }}}},{"runId":1,"streams.content.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1}) 
                objpar=lineage.find({'runId':runId,'streams.format':mtype,'parameters':{'$elemMatch':{'key':x,'val':{"$lte":maxval,"$gte":minval }}}},{"runId":1,"streams.content.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1}) 
                
                object_union=list(set(objdata).union(set(objpar)))
                
                
            else:
                
                objdata=lineage.find({'streams.format':mtype,'streams.content':{'$elemMatch':{x:{"$lte":maxval,"$gte":minval }}}},{"runId":1,"streams.content.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1}) 
                objpar=lineage.find({'streams.format':mtype,'parameters':{'$elemMatch':{'key':x,'val':{"$lte":maxval,"$gte":minval }}}},{"runId":1,"streams.content.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1})            
                object_union=list(set(objdata).union(set(objpar)))
                
            if (uniques!=None):
                uniques=list(set(uniques).intersection(set(object_union)))
                
            else:
           
                uniques=object_union
                
        
        totalCount=len(uniques)
          
        
               
        
        
                    
        artifacts = list()

        
        for x in  uniques:
            
            for s in x["streams"]:
                totalCount=totalCount+1
                s["wasGeneratedBy"]=x["_id"]
                s["parameters"]=x["parameters"]
                s["endTime"]=x["endTime"]
                s["startTime"]=x["startTime"]
                s["runId"]=x["runId"]
                s["errors"]=x["errors"]
                artifacts.append(s)
                    
        
                
        output = {"entities":artifacts};
        output.update({"totalCount": totalCount})
        return  output
        
        
    
    def getRunInfo(self, path):
         db = self.conection["verce-prov"]
         workflow = db['workflow']
         obj = workflow.find_one({"_id":path})
         return obj

         
     
    def getUserRuns(self, path, **kwargs):
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        obj=None
        totalCount=None
        output=None
        start=int(kwargs['start'][0])
        limit=int(kwargs['limit'][0])
        
        
        if 'activities' in kwargs:
            return self.getUserRunsValuesRange(kwargs['username'][0],None,None,None,**kwargs)
        else:
            obj = workflow.find({"username":path},{"_id":-1,"startTime":-1,"system_id":1,"description":1,"name":1,"workflowName":1,"grid":1,"resourceType":1,"resource":1,"queue":1}).sort("startTime",direction=-1)[start:start+limit]

        totalCount=workflow.find({"username":path}).count()
        runids = list()
        
        for x in obj:
                
            runids.append(x)
            
        output = {"runIds":runids};
        output.update({"totalCount": totalCount})
    
        return  output
    
    
    def num(self,s):
        try:
            return int(s)
        except exceptions.ValueError:
            return float(s)

     
    
    
    def getEntitiesBy(self,meth,keylist,mxvaluelist,mnvaluelist,vluelist,**kwargs):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        totalCount=0;
        cursorsList=list()
        obj=None
        
        start=int(kwargs['start'][0]) if 'start' in kwargs and kwargs['start'][0]!='null' else None
        limit=int(kwargs['limit'][0]) if 'limit' in kwargs and kwargs['limit'][0]!='null' else None
        runId=kwargs['runId'][0].strip() if 'runId' in kwargs and kwargs['runId'][0]!='null' else None
        dataId=kwargs['dataId'][0].strip() if 'dataId' in kwargs and kwargs['dataId'][0]!='null' else None
        iterationId=kwargs['iterationId'][0].strip() if 'iterationId' in kwargs and kwargs['iterationId'][0]!='null' else None
        mtype=kwargs['mime-type'][0].strip() if 'mime-type' in kwargs and kwargs['mime-type'][0]!='null' else None
        activities=None
        
        if 'activities' in kwargs:
            activities=str(kwargs['activities'][0]).split(',')
            
        i=0
        ' extract data by annotations either from the whole archive or for a specific runId'
         
        activ_searchDic={'_id':iterationId,'name':{'$in':activities},'runId':runId,'streams.format':mtype}
        
        activ_searchDic=clean_empty(activ_searchDic)
        
    
        
        
        if meth=="annotations":
            if runId!=None:
                for x in keylist:
                    cursorsList.append(lineage.find({'streams.annotations':{'$elemMatch':{'key': x,'val':{'$in':vluelist}}},'runId':runId},{"runId":1,"streams.annotations.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1,})[start:start+limit].sort("endTime",direction=-1))
                    totalCount = totalCount + lineage.find({'streams.annotations':{'$elemMatch':{'key': x,'val':{'$in':vluelist}}},'runId':runId},).count()
            else:
                for x in keylist:
                    cursorsList.append(lineage.find({'streams.annotations':{'$elemMatch':{'key': x,'val':{'$in':vluelist}}}},{"runId":1,"streams.annotations.$":1,'streams':1,'startTime':1,'endTime':1,'errors':1,"parameters":1})[start:start+limit].sort("endTime",direction=-1))
                    totalCount = totalCount + lineage.find({'streams.annotations':{'$elemMatch':{'key': x,'val':{'$in':vluelist}}}},).count()
        
        if meth=="generatedby":
            cursorsList.append(self.getEntitiesFilter(activ_searchDic,keylist,mxvaluelist,mnvaluelist,start,limit))
        elif meth=="run":        
            cursorsList.append(lineage.find({'runId':runId,'streams.id':dataId},{"runId":1,"streams":{"$elemMatch": { "id": dataId}},"parameters":1,'startTime':1,'endTime':1,'errors':1,'derivationIds':1}))
            totalCount = totalCount + lineage.find({'runId':runId,'streams.id':dataId}).count()
        elif meth=="values-range":
            cursorsList.append(self.getEntitiesFilter(activ_searchDic,keylist,mxvaluelist,mnvaluelist,start,limit))
        
        else:
            cursorsList.append(lineage.find({'streams.id':meth}))
                
            
        artifacts = list()

        for cursor in cursorsList:
            for x in cursor:
                
                for s in x["streams"]:
                     
                    if (mtype==None or mtype=="") or ('format' in s and s["format"]==mtype):
                        totalCount=totalCount+1
                        s["wasGeneratedBy"]=x["_id"]
                        s["parameters"]=x["parameters"]
                        s["endTime"]=x["endTime"]
                        s["startTime"]=x["startTime"]
                        s["runId"]=x["runId"]
                        s["errors"]=x["errors"]
                        s["derivationIds"]=x['derivationIds']
                        artifacts.append(s)
                    
        
                
        output = {"entities":artifacts};
        output.update({"totalCount": totalCount})
       
        return  output
         
    

    
    def editRun(self, id,doc):
        
        
        ret=[]
        response={}
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        lineage = db['lineage']
        try:
            
            workflow.update({"_id":id},{'$set':doc})
        
            response={"success":True}
            response.update({"edit":id}) 
        
        except Exception, err:
            response={"success":False}
            response.update({"error":str(err)})
            
        finally:
            return response
        
        
    def deleteRun(self, id):
        ret=[]
        response={}
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        lineage = db['lineage']
        try:
            if (workflow.find_one({"_id":id})!=None):
                lineage.remove({"runId":id})
                workflow.remove({"_id":id})
            
                response={"success":True}
                response.update({"delete":id}) 
            else:
                response={"success":False}
                response.update({"error":"Workflow run "+id+" does not exist!"}) 
            
        except Exception, err:
            response={"success":False}
            response.update({"error":str(err)})
            traceback.print_exc()
        finally:
            return response
    
    def insertWorkflow(self, json):
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        ret=[]
        response={}
        
        try:
            if type(json) =='list':
        
                for x in json:
                    
                    ret.append(workflow.insert(x))
            else:
                ret.append(workflow.insert(json))
        
            response={"success":True}
            response.update({"inserts":ret}) 
        
        except Exception, err:
            response={"success":False}
            response.update({"error":str(err)}) 
        finally:
            return response
    
    
    ' insert new data in different collections depending from the document type'

    def updateCollections(self, prov):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        workflow = db['workflow']
        try:
            if prov["type"]=="lineage":
                if prov["type"]=="lineage":
                #    return lineage.find_one_and_replace({'_id':prov['_id']},prov,upsert=True)
                # if(workflow.find_one({"_id":prov["runId"]})!=None):
                     return lineage.insert(prov)
                # else: 
                #     raise Exception("Workflow Run not found")

            if prov["type"]=="workflow_run":
             
                return workflow.insert(prov)
        
        except Exception, err:
            raise
            
    def insertData(self, prov):
        db = self.conection["verce-prov"]
        workflow = db['workflow']
        ret=[]
        response={}
        
        
        try:
            if type(prov).__name__ =='list':
                 
                for x in prov:
                   try:
                       ret.append(self.updateCollections(x))
                   except Exception, err:
                       ret.append({"error":str(err)})
            else:
                try:
                 
                    ret.append(self.updateCollections(prov))
                except Exception, err:
                       ret.append({"error":str(err)})
        
            response={"success":True}
            response.update({"inserts":ret}) 
        
        except Exception, err:
            
            response={"success":False}
            response.update({"error":str(err)}) 
            
        finally:
            return response
    
    
    def getDerivedDataTrace(self, id,level):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        xx = lineage.find_one({"streams.id":id},{"runId":1,"derivationIds":1,'streams.port':1,'streams.location':1});
        xx.update({"dataId":id})
        cursor=lineage.find({"derivationIds":{'$elemMatch':{"DerivedFromDatasetID":id}}},{"runId":1,"streams":1});
         
        
        if level>0:
            derivedData=[]
            
            i=0
            for d in cursor:
                i+=1
                if (i<25):
                 
                 
                 
                    for str in d["streams"]:
                     
                        try:
                            derivedData.append(self.getDerivedDataTrace(str["id"],level-1))
                        
                        except Exception, err:
                            None
                 
                 
                
            xx.update({"derivedData":derivedData})
                
            
         
        
      
        return xx
    
    def getTraceX(self, id,level):
        db = self.conection["verce-prov"]
         
        lineage = db['lineage']
        if type(id)==list:
            xx = lineage.find({"streams.id":{"$in":id}});
        else:
            xx = lineage.find_one({"streams.id":id});

        xx.update({"id":id})
        if level>=0:
            
            try:
                derid["wasDerivedFrom"] = self.getTrace(derid["DerivedFromDatasetID"],level-1)
            except Exception, err:
                None
            return xx


    def getTrace(self, id,level):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        xx = lineage.find_one({"streams.id":id});
        if type(id)==list:
            xx = lineage.find({"streams.id":{"$in":id}});
        else:
            xx = lineage.find_one({"streams.id":id});
       # xx.update({"id":id})
        if level>=0:
            
            for derid in x["derivationIds"]:
                try:
                    derid["s-prov:Data"] = self.getTrace(derid["DerivedFromDatasetID"],level-1)
                except Exception, err:
                    None
            return xx


    def getTrace(self, id,level):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        xx = lineage.find_one({"streams.id":id},{'streams':{'$elemMatch':{'id':id}},
                                                            'iterationId':1,
                                                            'runId':1,
                                                            'streams.location':1,
                                                            'actedOnBehalfOf':1,
                                                            'derivationIds':1,
                                                            '_id':0}
                                                            );
        
        #xx.update({"id":id})
        

        if level>=0:
            
            for derid in xx["derivationIds"]: 
                try:
                    derid["s-prov:Data"] = {"@id":derid["DerivedFromDatasetID"]}
                    derid["wasDerivedFrom"] = self.getTrace(derid["DerivedFromDatasetID"],level-1)
                     
                    if (derid["wasDerivedFrom"]):
                        derid["s-prov:Data"] = derid["wasDerivedFrom"]["s-prov:Data"]
                        del derid["wasDerivedFrom"]
                        del derid["DerivedFromDatasetID"]
                        del derid["TriggeredByProcessIterationID"]
                    else:
                        derid.clear()
                         

                  


                except Exception, err:
                    traceback.print_exc()
            
            xx["s-prov:Data"]=xx['streams'][0]
            xx["s-prov:Data"]['@id']=xx["s-prov:Data"]['id']
            xx["s-prov:Data"]['prov:location']=xx["s-prov:Data"]['location']
            xx["s-prov:Data"]['prov:hadMember']=xx["s-prov:Data"]['content']
            xx["s-prov:Data"]['prov:Derivation']=xx["derivationIds"]
            xx["s-prov:Data"]["prov:wasGeneratedBy"]={}
            xx["s-prov:Data"]["prov:wasGeneratedBy"]['s-prov:Invocation']={'@id':xx['iterationId']}
            xx["s-prov:Data"]["prov:wasGeneratedBy"]['s-prov:WFExecution']={'@id':xx['runId']}
            xx["s-prov:Data"]["prov:wasAttributedTo"]={'@id':xx['actedOnBehalfOf'],'@type':'s-prov:Component'}
            del xx["s-prov:Data"]['location']
            del xx["s-prov:Data"]['content']
            del xx["s-prov:Data"]['id']
            del xx['iterationId']
            del xx['runId']
            del xx["actedOnBehalfOf"]
            del xx["derivationIds"]
            del xx['streams']
            return xx
        
        
    def getTraceList(self, id,level,ll):
        sys.setrecursionlimit(2000)
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        xx = lineage.find_one({"streams.id":id});
        xx.update({"id":id})
        ll.append(xx)
        if level>=0:
            for derid in xx["derivationIds"]:
                if 'DerivedFromDatasetID' in derid and derid["DerivedFromDatasetID"]!=None and derid["DerivedFromDatasetID"]!=xx["id"]:
                    try:
                    
                        self.getTraceList(derid["DerivedFromDatasetID"],level-1,ll)
                    
                    except Exception, err:
                        traceback.print_exc()
                 
            return xx
        
        
        
  
        
    
    
    def filterOnAncestorsValuesRange(self,idlist,keylist,minvaluelist,maxvaluelist):
        filteredIds=[]
        for x in idlist:
            test=self.hasAncestorWithValuesRange(x,keylist,minvaluelist,maxvaluelist)
         
            if test!=None and test["hasAncestorWith"]==True:
                filteredIds.append(x)
        
        return filteredIds
    
    def filterOnAncestorsMeta(self,idlist,keylist,valuelist):
        filteredIds=[]
        for x in idlist:
            test=self.hasAncestorWith(x,keylist,valuelist)
         
            if test["hasAncestorWith"]==True:
                filteredIds.append(x)
        
        return filteredIds
    
    def filterOnMeta(self,idlist,keylist,valuelist):
        filteredIds=[]
        for x in idlist:
            test=self.hasMeta(x,keylist,valuelist)
        
            if test["hasMeta"]==True:
                filteredIds.append(x)
        
        return filteredIds
            
    
    def hasMeta(self, id, keylist,valuelist):
         
        elementsDict ={}
        
        k=0
        for x in keylist:
            val=valuelist[k]
            k+=1
            try: 
                val =self.num(val)
            except Exception,e:
                None

            elementsDict.update({x:val})
        
        xx = lineage.find_one({"streams":{"$elemMatch":{"id":id,'content':{'$elemMatch':elementsDict}}}},{"streams.id":1});
        if (xx!=None):    
            
            return {"hasMeta":True}
                    
                  
        else:
            return {"hasMeta":False}
    
                
    def hasAncestorWithValuesRange(self, id, keylist,minvaluelist,maxvaluelist):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        elementsDict ={}
        k=0
        for x in keylist:
            maxval=maxvaluelist[k]
            minval=minvaluelist[k]
            k+=1
            try: 
                maxval =self.num(maxval)
                minval =self.num(minval)
            except Exception,e:
                None
                

            elementsDict.update({x:{"$lte":maxval,"$gte":minval }})
         
        xx = lineage.find_one({"streams.id":id},{"runId":1,"derivationIds":1});
        if xx!= None and len(xx["derivationIds"])>0:    
            for derid in xx["derivationIds"]:
                try:
                
                    anchestor = lineage.find_one({"streams":{"$elemMatch":{"id":derid["DerivedFromDatasetID"],'content':{'$elemMatch':elementsDict}}}},{"streams.id":1});
                    
                    if anchestor!=None:
                        return {"hasAncestorWith":True}
                    else:
                        return self.hasAncestorWithValuesRange(derid["DerivedFromDatasetID"],keylist,minvaluelist,maxvaluelist)
                except Exception,e: 
                   traceback.print_exc()
        else:
            return {"hasAncestorWith":False}
        
    
    def hasAncestorWith(self, id, keylist,valuelist):
         
        elementsDict ={}
        
        k=0
        for x in keylist:
            val=valuelist[k]
            k+=1
            try: 
                val =self.num(val)
            except Exception,e:
                None

            elementsDict.update({x:val})
        
        xx = lineage.find_one({"streams.id":id},{"runId":1,"derivationIds":1});
        if len(xx["derivationIds"])>0:    
            for derid in xx["derivationIds"]:
                try:
                
                    anchestor = lineage.find_one({"streams":{"$elemMatch":{"id":derid["DerivedFromDatasetID"],'content':{'$elemMatch':elementsDict}}}},{"streams.id":1});
                    
                    if anchestor!=None:
                        return {"hasAncestorWith":True}
                    else:
                        return self.hasAncestorWith(derid["DerivedFromDatasetID"],keylist,valuelist)
                except Exception,e: 
                   traceback.print_exc()
        else:
            return {"hasAncestorWith":False}
       
        
        
    def getTraceConditonalX(self, id, keylist,valuelist):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        elementsDict ={}
        
        k=0
        for x in keylist:
            val=valuelist[k]
            k+=1
            try: 
                val =self.num(val)
            except Exception,e:
                None

            elementsDict.update({x:val})
        
        xx = lineage.find_one({"streams.id":id,'streams.content':{'$elemMatch':elementsDict}},{"runId":1,"derivationIds":1});
        
        if xx==None:
            xx = lineage.find_one({"streams.id":id},{"runId":1,"derivationIds":1});
             
            xx.update({"id":id})
            
            for derid in xx["derivationIds"]:
                try:
                    val = self.getTraceConditonal(derid["DerivedFromDatasetID"],keylist,valuelist)
                     
                    if val!=None:
                        return {"hasAnchestor":True}
                    
                except Exception, err:
                    traceback.print_exc()
            
        else:
            return xx
        
        
    def getActivitiesSummaries(self,**kwargs): 
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        workflow = db['workflow']
        obj=[]
        runId=[]
        groupby=None
        clusters=None
        tags=None
        run=None
        users=None
        if 'users' in kwargs :
            memory_file = StringIO.StringIO(kwargs['users'][0]);
            users = csv.reader(memory_file).next()
            
       # if 'tags' in kwargs : 
       #     memory_file = StringIO.StringIO(kwargs['tags'][0]);
       #     tags = csv.reader(memory_file).next()
       #     runIdlist=workflow.aggregate(pipeline=[{'$match':{'tags':{'$in':tags}}},{'$project':{'_id':1}}])
       #     for y in runIdlist:
       #         runId.append(y['_id'])
                 
        else:
            if 'runId' in kwargs : runId = kwargs['runId'][0]


        if 'groupby' in kwargs:
            groupby=kwargs['groupby'][0]
        if 'clusters' in kwargs:
            memory_file = StringIO.StringIO(kwargs['clusters'][0]);
            clusters = csv.reader(memory_file).next()
       
        matchdic=clean_empty({'username':{'$in':users},'runId':runId, 'prov_cluster':{'$in':clusters} })
        
        
        start=dateutil.parser.parse(kwargs['starttime'][0]) if 'starttime' in kwargs and kwargs['starttime'][0]!='null' else None
        matchdic=clean_empty(matchdic)
        
        if 'level' in kwargs and kwargs['level'][0]=='prospective':
            obj=lineage.aggregate(pipeline=[{'$match':matchdic},{'$unwind': "$streams"},{'$group':{'_id':{'actedOnBehalfOf':'$actedOnBehalfOf','mapping':'$mapping',str(groupby):'$'+str(groupby)}, 'time':{'$min': '$startTime'}}},{'$sort':{'time':1}}]) 
            
        elif 'level' in kwargs and kwargs['level'][0]=='iterations':
            matchdic.update({'startTime':{'$gt':str(start)},'iterationIndex':{'$gte':int(kwargs['minidx'][0]) ,'$lt':int(kwargs['maxidx'][0])}})
            matchdic=clean_empty(matchdic)
            obj=lineage.aggregate(pipeline=[{'$match':matchdic},{'$match':matchdic},{'$unwind': "$streams"},{'$group':{'_id':{'iterationId':'$iterationId','mapping':'$mapping',str(groupby):'$'+str(groupby)}, 'time':{'$min': '$startTime'}}},{'$sort':{'time':1}}])
        elif 'level' in kwargs and kwargs['level'][0]=='instances':
            obj=lineage.aggregate(pipeline=[{'$match':matchdic},{'$unwind': "$streams"},{'$group':{'_id':{'instanceId':'$instanceId','mapping':'$mapping',str(groupby):'$'+str(groupby)}, 'time':{'$min': '$startTime'}}},{'$sort':{'time':1}}])
        elif 'level' in kwargs and (kwargs['level'][0]=='vrange' or kwargs['level'][0]=='data'):

            memory_file = StringIO.StringIO(kwargs['keys'][0]);
            keylist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(kwargs['maxvalues'][0]);
            mxvaluelist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(kwargs['minvalues'][0]);
            mnvaluelist = csv.reader(memory_file).next()
            memory_file = StringIO.StringIO(kwargs['users'][0]);
            users = csv.reader(memory_file).next()
            #memory_file = StringIO.StringIO(kwargs['tags'][0]);
            #tags = csv.reader(memory_file).next()
            
            searchDic = self.makeElementsSearchDic(keylist,mnvaluelist,mxvaluelist)
             
            #print(" searchdic "+json.dumps(searchDic['streams.content']['$elemMatch']))
            if kwargs['level'][0]=='vrange':
                if kwargs['mode'][0]=="AND":
                    obj=lineage.aggregate(pipeline=[{'$match':{'username':{'$in':users},'streams.content':searchDic['streams.content']}},{'$group':{'_id': {'runId':'$runId','username':'$username', str(groupby):'$'+str(groupby)}}}])
                elif kwargs['mode'][0]=="OR":
                    for y in searchDic['streams.content']['$elemMatch']:
                        for c in lineage.aggregate(pipeline=[{'$match':{'username':{'$in':users},'streams.content':{'$elemMatch':{y:searchDic['streams.content']['$elemMatch'][y]}}}},{'$group':{'_id': {'runId':'$runId','username':'$username'}}}]):
                            obj.append(c)
                
        else:
            obj=lineage.aggregate(pipeline=[{'$match':{'runId':{'$in':runId}}},{'$group':{'_id':{'name':'$name'}}},{'$project':{'_id':1}}]) 
       
        
        connections=[]
        
        
        for x in obj:
             
            #add=True
            if not bool(x):
               del x
            
            if runId:
                 
                #run=x['_id']['run']
                x['_id'].update({'runId':runId})
                 
                #del x['_id']['run']
            
            trigger_cursor=None
            tringgers=[]
            if 'level' in kwargs and kwargs['level'][0]=='vrange':
                try:
                    
                    trigger_cursor=workflow.aggregate(pipeline=[{'$match':{'_id':x['_id']['runId']}},{'$unwind':'$input'},{'$match':{'$or':[{'input.prov:type':'wfrun'},{'input.prov-type':'wfrun'}]}},{'$project':{'input.url':1,'_id':0}}])
                    print 'TRIG '+str(x['_id'])+' '+ json.dumps(triggers)
                except:
                    traceback.print_exc()
                    triggers=[]
                
                    #print "wf ID "+str(x['_id'])
                try:

                    wfitem=workflow.find({'_id':x['_id']['runId']},{groupby:1,'_id':0})[0]
                    if groupby in wfitem:
                        x['_id'].update(wfitem) 
                    else:
                        continue
                        #print "wfname"+str(wfitem['workflowName'])
                except:
                    traceback.print_exc()
                    print "wf ID "+str(x['_id']['runId'])+" not found inf workflow collection"
                    del x
                    continue
                     
                     
            elif 'level' in kwargs and (kwargs['level'][0]=='instances' or kwargs['level'][0]=='iterations' or kwargs['level'][0]=='prospective'):
                trigger_cursor=lineage.aggregate(pipeline=[{'$match':x['_id']},{'$unwind':'$derivationIds'},{'$group':{'_id':'$derivationIds.DerivedFromDatasetID'}}])  
            elif 'level' in kwargs and kwargs['level'][0]=='data':
                trigger_cursor=lineage.aggregate(pipeline=[{'$match':{'streams.id':x['_id']['id']}},{'$unwind':'$derivationIds'},{'$project':{'_id':0,'id':'$derivationIds.DerivedFromDatasetID'}}]) 

            triggers=[]
            
            for t in trigger_cursor:
                #print(t)
                if '_id' in t and t['_id']!=None:
                    
                    
                    triggers.append(t['_id'])
                else:
                    triggers.append(t)
               
                
                
            
            
            
            if len(triggers)>0:
                #print "triggers "+str(x['_id'])+" "+str(triggers)
                pes=[]
                #print "DOING CONN"
                 
                if 'level' in kwargs and kwargs['level'][0]=='prospective':
                    pes=lineage.aggregate(pipeline=[{'$match':{'streams.id':{'$in':triggers}}},{'$unwind':'$streams'},{'$group':{'_id':{'actedOnBehalfOf':'$actedOnBehalfOf'},'size':{'$sum':'$streams.size'}}}])
                elif 'level' in kwargs and kwargs['level'][0]=='iterations':
                    pes=lineage.aggregate(pipeline=[{'$match':{'streams.id':{'$in':triggers}}},{'$unwind':'$streams'},{'$group':{'_id':{'iterationId':'$iterationId'},'size':{'$sum':'$streams.size'}}}])
                elif 'level' in kwargs and kwargs['level'][0]=='instances':
                    pes=lineage.aggregate(pipeline=[{'$match':{'streams.id':{'$in':triggers}}},{'$unwind':'$streams'},{'$group':{'_id':{'instanceId':'$instanceId'},'size':{'$sum':'$streams.size'}}}]) 
                elif 'level' in kwargs and kwargs['level'][0]=='vrange':
                    for w in triggers:
                        up=urlparse(w['input']['url']).path
                        up=up[up.rfind('/')+1:len(up)+1]
                         
                        curs=workflow.find({'_id':up})
                        if (curs.count()>0):
                            pes.append(up)
                elif 'level' in kwargs and kwargs['level'][0]=='data':
                    pes=triggers
                else:
                    pes=lineage.aggregate(pipeline=[{'$match':{'$or':triggers}},{'$project':{'name':1,"_id":0}}]) 
                
                #x['_id']['runId']=run
                pelist=[]
                
                for pe in pes:
                    
                    pelist.append(pe)
                    
                    
                x.update({'name':x['_id'], 'connlist':pelist})
                
                #print "connections done for: "+str(x['_id'])+" PES:"+str(pelist)
                #print "size for: "+str(x['_id'])+" PES:"+str(len(pes))
                
                
                del x['_id']
                connections.append(x)
                
                 
#             
            else: 
                 
                x.update({'name':x['_id'], 'connlist':[]})
                del x['_id']
                connections.append(x)
                
        return connections
    
    
    ' methods for the updated API'
    
    def getEntitiesGeneratedBy(self,runid,invocationid,start,limit):
        cursorsList=[]
        activ_searchDic={'iterationId':invocationid,'runId':runid}
        cursorsList.append(self.getEntitiesFilter(activ_searchDic,None,None,None,start,limit))
        entities=[]
        
        totalCount=0
        for cursor in cursorsList:
            for x in cursor:
                 
                for s in x["streams"]:
                     
                    totalCount=totalCount+1
                    s["wasGeneratedBy"]=x["iterationId"]
                    s["parameters"]=x["parameters"]
                    s["endTime"]=x["endTime"]
                    s["startTime"]=x["startTime"]
                    s["runId"]=x["runId"]
                    s["errors"]=x["errors"]
                    s["derivationIds"]=x['derivationIds']
                    entities.append(s)
                    
        
                
        output = {"entities":entities};
        output.update({"totalCount": totalCount})
       
        return  output


    def getEntitiesAttributedToInstnace(self,runid,instanceId,start,limit):
        cursorsList=[]
        activ_searchDic={'instanceId':instanceId,'runId':runid}
        cursorsList.append(self.getEntitiesFilter(activ_searchDic,None,None,None,start,limit))
        entities=[]
        
        totalCount=0
        for cursor in cursorsList:
            for x in cursor:
                 
                for s in x["streams"]:
                     
                    totalCount=totalCount+1
                    s["wasGeneratedBy"]=x["iterationId"]
                    s["parameters"]=x["parameters"]
                    s["endTime"]=x["endTime"]
                    s["startTime"]=x["startTime"]
                    s["runId"]=x["runId"]
                    s["errors"]=x["errors"]
                    s["derivationIds"]=x['derivationIds']
                    entities.append(s)
                    
        
                
        output = {"entities":entities};
        output.update({"totalCount": totalCount})
       
        return  output


    # new methods for new API returning JSON-LD


    def addLDContext(self,obj):
        obj["@context"]={"s-prov" : "https://raw.githubusercontent.com/KNMI/s-provenance/master/resources/s-prov-o.owl#",
                            "prov" : "http://www.w3.org/ns/prov-o#",
                            "oa" : "http://www.w3.org/ns/oa.rdf#",
                            "vcard" : "http://www.w3.org/2006/vcard/ns#",
                            "provone" : "http://purl.org/provone"}
        return obj

    def getMonitoring(self, id,level,start,limit):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        group=''
        if level=="invocation":
               group='iterationId'
        elif level=="instance":
               group='instanceId'

        obj = lineage.aggregate(pipeline=[{'$match':{'runId':id}},
                                                    
                                                    {"$unwind":"$streams"},
                                                    {'$group':{'_id':'$'+group, 
                                                     "s-prov:lastEventTime":{"$max":"$endTime"}, 
                                                     "s-prov:message":{"$push":"$errors"},
                                                     "s-prov:worker":{"$first":"$worker"},
                                                     "prov:actedOnBehalfOf":{"$first":"$actedOnBehalfOf"}, 
                                                     "s-prov:generatedWithImmediateAccess":{"$push":"$streams.con:immediateAccess"},
                                                     "s-prov:generatedWithLocation":{"$push":"$streams.location"},
                                                     "s-prov:qualifiedChange": {"$push":"$s-prov:qualifiedChange"},
                                                     "s-prov:count":{"$push":"$streams.id"}}},
                                                     {"$sort":{"s-prov:lastEventTime":-1}},
                                                     {'$skip':start},
                                                     {'$limit':limit},
                                                     ])

        count = lineage.aggregate(pipeline=[{'$match':{'runId':id}},
                                                    {'$group':{'_id':'$'+group}},
                                                    {"$count":group}])
        for x in count:
            totalCount=x[group]
#{'$project':{"runId":1,"instanceId":1,"parameters":1,"endTime":-1,"errors":1,"iterationIndex":1,"iterationId":1,"streams.con:immediateAccess":1,"streams.location":1}
       # lineage.find({'runId':id},{"runId":1,"instanceId":1,"parameters":1,"endTime":-1,"errors":1,"iterationIndex":1,"iterationId":1,"streams.con:immediateAccess":1,"streams.location":1})[start:start+limit].sort("endTime",direction=-1)
         
        activities = list()
        
        for x in obj:
           x['@id']=x['_id']
           del x['_id']
           if level=="invocation":
               x['@type']='s-prov:Invocation'
           elif level=="instance":
               x['@type']='s-prov:ComponentInstance'

           activities.append(x)

           x['s-prov:message']=''.join(x['s-prov:message'])
           
           if type(x['s-prov:generatedWithLocation'])==list:
                flat_list=[]
                for sublist in x['s-prov:generatedWithLocation']:
                    for item in sublist:
                        flat_list.append(item)
                x['s-prov:generatedWithLocation']=flat_list

           x['s-prov:generatedWithLocation']=''.join(x['s-prov:generatedWithLocation'])
           x['s-prov:generatedWithLocation']=True if x['s-prov:generatedWithLocation']!="" else False
           x['s-prov:generatedWithImmediateAccess']= True if ("true" in x['s-prov:generatedWithImmediateAccess'] or True in x['s-prov:generatedWithImmediateAccess']) else False
           #x['s-prov:hasChanged']=True if len(x['feedbackInvocation'])!=0 else False
           x['s-prov:count'] = len(x['s-prov:count'])
           x['prov:actedOnBehalfOf'] = {"@type":"s-prov:Component", "@id":x['prov:actedOnBehalfOf']}
           
           
            
        output = {"@graph":activities};
  
        output=self.addLDContext(output)
        output["totalCount"]= totalCount
        return  output


    def getComponentInstance(self, id):
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        obj = lineage.aggregate(pipeline=[{'$match':{'instanceId':id}},
                                                    {"$unwind":"$streams"},
                                                    {"$sort":{"endTime":-1}},
                                                    {'$group':{'_id':'$instanceId', 
                                                     "s-prov:lastEventTime":{"$max":"$endTime"}, 
                                                     "s-prov:message":{"$push":"$errors"},
                                                     "worker":{"$first":"$worker"}, 
                                                     "s-prov:generatedWithImmediateAccess":{"$push":"$streams.con:immediateAccess"},
                                                     "s-prov:generatedWithLocation":{"$push":"$streams.location"},
                                                     "s-prov:count":{"$push":"$streams.id"},
                                                     "pid" : {"$first":"$pid"},
                                                     "mapping" : {"$first":"$mapping"},
                                                     "s-prov:qualifiedChange": {"$push":"$s-prov:qualifiedChange"},
                                                     "s-prov:ComponentParameters": {"$first":"$parameters"},
                                                     "prov:contributed":{"$first":"$name"}, 
                                                     "prov:actedOnBehalfOf":{"$first":"$actedOnBehalfOf"}, 
                                                     "prov_cluster":{"$first":"$prov_cluster"}}}
                                                     #{ "$project": { "@id":"$_id", "_id":0, "s-prov:worker":1, "s-prov:lastEventTime":1, "s-prov:message":1,"s-prov:generatedWithImmediateAccess":1,"s-prov:generatedWithLocation":1,"s-prov:count":1}}
                                                    ]) 
        
        output={}
        count = lineage.aggregate(pipeline=[{'$match':{'instanceId':id}},
                                                    {'$group':{'_id':'$instanceId'}},
                                                    {"$count":'instanceNum'}])

        for x in count:
            totalCount=x['instanceNum']


        for x in obj:
            
            x['@id']=x['_id']
            x['@type']='s-prov:ComponentInstance'
            x['prov:type']='s-prov:ComponentInstance'
            x['prov:atLocation']= {"@type" : "s-prov:SystemProcess",
                "s-prov:pid" : x["pid"],
                "s-prov:mapping" : x["mapping"],
                "s-prov:worker" : x["worker"]}

            x['prov:actedOnBehalfOf'] = {"@type":"s-prov:Component", "@id":x['prov:actedOnBehalfOf']}
            x['prov:contributed'] = {"@type":"s-prov:Implementation", "@id":x['prov:contributed']}

            
            x['s-prov:message']=''.join(x['s-prov:message'])
           
            if type(x['s-prov:generatedWithLocation'])==list:
                flat_list=[]
                for sublist in x['s-prov:generatedWithLocation']:
                    for item in sublist:
                        flat_list.append(item)
                x['s-prov:generatedWithLocation']=flat_list

            x['s-prov:generatedWithLocation']=''.join(x['s-prov:generatedWithLocation'])
            x['s-prov:generatedWithLocation']=True if x['s-prov:generatedWithLocation']!="" else False
            x['s-prov:generatedWithImmediateAccess']= True if ("true" in x['s-prov:generatedWithImmediateAccess'] or True in x['s-prov:generatedWithImmediateAccess']) else False
            x['s-prov:count'] = len(x['s-prov:count'])


             
            
            del x['_id']
            del x["pid"]
            del x["mapping"]
            del x["worker"]
            del x['prov_cluster']
            
            output=x

        output=self.addLDContext(output)
        output["totalCount"]= totalCount
        return output


    def getData(self,start,limit,genBy=None,attrTo=None,keylist=None,maxvalues=None,minvalues=None,id=None):
    
        db = self.conection["verce-prov"]
        lineage = db['lineage']
        totalCount=0;
        searchAgents=None
        searchActivities=None
        cursorsList=[]
        
        activities=None
        
        if attrTo!=None:
            agents=attrTo.split(',')
            searchAgents=[{'actedOnBehalfOf':{'$in':agents}},{'instanceId':{'$in':agents}},{'username':{'$in':agents}}]
            

        if genBy!=None:
            activities=genBy.split(',')
            searchActivities=[{'name':{'$in':activities}},{'iterationId':{'$in':activities}},{'runId':{'$in':activities}}]
        


            
        i=0
        ' extract data by annotations either from the whole archive or for a specific runId'
         
        searchDic={"$and":[{"$or":searchAgents},{"$or":searchActivities}]}
        searchDic=clean_empty(searchDic)
         
        
        
        
         
        if searchDic!=None:
            (obj,totalCount)=self.getEntitiesFilter(searchDic,keylist,maxvalues,minvalues,start,limit)
            cursorsList.append(obj)
        #elif meth=="values-range":
        #    cursorsList.append(self.getEntitiesFilter(activ_searchDic,keylist,mxvaluelist,mnvaluelist,start,limit))
        
        else:
            cursorsList.append(lineage.find({'streams.id':id}))
                
            
        artifacts = list()

        for cursor in cursorsList:
            for x in cursor:
                
                for s in x["streams"]:
                     
                    #if (mtype==None or mtype=="") or ('format' in s and s["format"]==mtype):
                     
                    s["wasGeneratedBy"]=x["_id"]
                    s["parameters"]=x["parameters"]
                    s["endTime"]=x["endTime"]
                    s["startTime"]=x["startTime"]
                    s["runId"]=x["runId"]
                    s["errors"]=x["errors"]
                    s["derivationIds"]=x['derivationIds']
                    artifacts.append(s)
                    
        
                
        output = {"@graph":artifacts};
        output=self.addLDContext(output)
        output.update({"totalCount": totalCount})
       
        return  output
        






        
    