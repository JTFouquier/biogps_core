setVisible=function(b,c){var a=b.style;a.visibility=c?"visible":"hidden"};String.prototype.trim=function(){return this.replace(/^\s*/,"").replace(/\s*$/,"")};String.prototype.capitalize=function(){return this.charAt(0).toUpperCase()+this.slice(1)};coreDispatcher={showWelcome:true,delayedAction:null,biogpsLoaded:function(){return(window.biogps&&biogps.renderMainUI)!=null},delayedExecute:function(a){if(coreDispatcher.biogpsLoaded()){ga("send","event","coreDispatcher.delayedExecute","callback",{nonInteraction:1});a()}else{ga("send","event","coreDispatcher.delayedExecute","delaying",{nonInteraction:1});this.delayedAction=a}},isMainUICommand:function(b){if(!(b&&b.toLowerCase)){return false}b=b.toLowerCase();var c=["genereport","mystuff","pluginlibrary","about","help","faq","downloads","terms"];for(var a=0;a<c.length;a++){if(b==c[a]){return true}}return false},dispatch:function(){var d=window.location.hash;if(d.length>0&&d.substring(0,1)=="#"){d=d.substring(1);var c=null;var e=d.split("&");for(var b=0;b<e.length;b++){var a=e[b].split("=");if(a[0]=="goto"&&a.length>1){c=a[1];break}}if(this.isMainUICommand(c)){this.showWelcome=false}}else{window.location.hash="#goto=welcome"}},hideWelcome:function(b){this.ieBackButtonFix();var a=document.getElementById("welcome");setVisible(a,false);coreDispatcher.showWelcome=false},hideSymatlas:function(a){ga("send","event","SymAtlas","Start BioGPS",a,{nonInteraction:1});if(a.length>0){window.location.href="/?query="+a}else{var b=document.getElementById("symatlas-mask");setVisible(b,false);b=document.getElementById("symatlas-box");setVisible(b,false);document.getElementById("qsearch_query").focus()}},goBacktoSymatlas:function(a){ga("send","event","SymAtlas","Back to SymAtlas",query,{nonInteraction:1});window.location="http://symatlas.gnf.org/deprecated/"+a},useSampleSearch:function(c,a){if(a){a.cancelBubble=true}var b=document.getElementById("qsearch_query");b.value=c;b.focus()},bindHotKey:function(){var b=Ext.get("qsearch_form");var a=new Ext.KeyMap(b,{key:13,ctrl:true,stopEvent:true,fn:function(){b.dom.onsubmit()},scope:this})},ieBackButtonFix:function(){if(Ext.isIE){Ext.History.suspendEvents();Ext.History.add("goto=welcome");Ext.History.resumeEvents()}},doSearch_v1:function(c,a){if(a){a.cancelBubble=true}var b=c.query.value.trim();if(b!=""){var d=c.qtype.value;this.delayedExecute(function(){biogps.Messenger.on("genelistrendered",function(){coreDispatcher.hideWelcome();biogps.clearListeners(biogps.Messenger,"genelistrendered")});biogps.doSearch({query:b,qtype:d,searchby:"searchbyanno",target:c.query.id})})}else{c.query.value="";c.query.focus()}},doSearch:function(d,a){if(a){a.cancelBubble=true}var b=d.query.value.trim();var c=d.userfilter?d.userfilter.value:null;if(b!=""){this.delayedExecute(function(){biogps.Messenger.on("genelistrendered",function(){coreDispatcher.hideWelcome();biogps.clearListeners(biogps.Messenger,"genelistrendered")});biogps.doSearch({query:b,userfilter:c,target:d.query.id})})}else{d.query.value="";d.query.focus()}},gotoSearch:function(a){if(a){a.cancelBubble=true}this.delayedExecute(function(){coreDispatcher.hideWelcome();Ext.History.add("goto=search")})},doTopBarSearch:function(c,a){if(a){a.cancelBubble=true}var b=c.topquery.value.trim();c.topquery.value="";c.topquery.blur();if(b!=""&&b!="Quick gene search"){ga("send","event","BioGPS","QuickGeneSearch",b,{nonInteraction:1});window.location="/#goto=search&query="+b}return false},onInputFocus:function(b,a){if(a){a.cancelBubble=true}if(b.value==b.defaultValue){b.value="";b.className=""}return false},onInputBlur:function(b,a){if(a){a.cancelBubble=true}if(b.value.trim()==""){b.value=b.defaultValue;b.className="inactive"}return false},openid:function(c){var b=document.getElementById("openid_url");var a=document.getElementById("openid_form");ga("send","pageview","/auth/login/openid/"+c);if(c=="google"){b.value="https://www.google.com/accounts/o8/id";a.submit()}else{if(c=="yahoo"){b.value="http://yahoo.com/";a.submit()}}},onGoogleGroupsSignup:function(a,b){if(a){a.cancelBubble=true}this.delayedExecute(function(){biogps.subscribeGoogleGroups(a,Ext.get(b))})}};biogps={};biogps.bequietonfailure=false;window.onbeforeunload=function(){biogps.bequietonfailure=true};