/* Personal information editor. It never sends writes or credentials to a service. */
(() => {
  'use strict';
  const sections = {basics:'基本资料',profile:'首页简介与研究兴趣',work:'工作经历',education:'学历与导师',publications:'论文',theses:'学位论文',awards:'奖励与资助',presentations:'报告与研讨会',conferences:'会议与访问',teaching:'课程',supervision:'指导经历',skills:'语言与软件'};
  const labels = {name:'姓名',email:'CV 邮箱',institutionalEmail:'学校邮箱（侧栏）',website:'网站地址（仅用于网页）',orcid:'ORCID 编号',github:'GitHub 用户名',googleScholar:'Google Scholar 链接',arxiv:'arXiv 编号或链接',avatar:'头像文件名',researchInterests:'研究兴趣（仅显示在首页）',industrySummary:'行业经历简介（仅显示在首页）',researchArea:'研究领域',position:'职位',department:'部门',organization:'机构',organizationShort:'机构简称',url:'网页链接',startDate:'开始日期',endDate:'结束日期（当前工作留空）',summary:'补充说明',degree:'学位',area:'专业',institution:'学校',departmentUrl:'部门链接',program:'培养项目',supervisorRole:'导师称谓',thesisHost:'论文所在机构',thesisHostUrl:'论文所在机构链接',title:'标题',year:'年份',status:'状态',journal:'期刊',note:'备注',date:'日期',homepage:'显示在对应网页列表（PDF 始终保留）',event:'活动或邀请单位',location:'地点',course:'课程名',role:'身份',term:'学期',items:'项目（每行一项）'};
  const schemas = {
    basics:['name','email','institutionalEmail','website','orcid','github','googleScholar','arxiv','avatar'],profile:['researchInterests','industrySummary','researchArea'],
    work:['position','department','organization','organizationShort','url','startDate','endDate','summary'],education:['degree','area','institution','url','department','departmentUrl','program','endDate','supervisorRole','supervisors','thesisHost','thesisHostUrl'],
    publications:['title','authors','year','status','journal','arxiv','url','note'],theses:['title','year','url'],awards:['title','organization','startDate','date','homepage'],presentations:['title','event','location','date','status','homepage'],conferences:['title','location','startDate','date','note'],teaching:['course','institution','role','date','term','homepage'],supervision:['role','organization','startDate','date'],skills:['name','items']
  };
  const required = {basics:['name','email','institutionalEmail','website','orcid','avatar'],profile:['researchInterests','industrySummary','researchArea'],work:['position','organization','startDate'],education:['degree','area','institution','endDate','supervisorRole'],publications:['title','year','status'],theses:['title','year','url'],awards:['title','date'],presentations:['title','event','date','status'],conferences:['title','date'],teaching:['course','institution','role','date'],supervision:['role','organization','date'],skills:['name']};
  const source = 'https://raw.githubusercontent.com/pandamology/pandamology.github.io/master/_data/cv.json';
  const $ = id => document.getElementById(id);
  let data, base, changed = false, section = 'publications', busy = false;
  function node(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
  function message(text,error=false){$('editor-status').textContent=text;$('editor-status').classList.toggle('error',error);}
  function dirty(){changed=true;message('有尚未提交的修改。填写完成后，请下载更新文件并在 GitHub 上传提交。');}
  function download(filename){const blob=new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'});const url=URL.createObjectURL(blob);const a=node('a');a.href=url;a.download=filename;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),10000);}
  function button(text,fn){const b=node('button',text);b.type='button';b.addEventListener('click',fn);return b;}
  function validDate(s){if(!/^\d{4}(?:-\d{2})?(?:-\d{2})?$/.test(s))return false;const [y,m=1,d=1]=s.split('-').map(Number);const t=new Date(Date.UTC(y,m-1,d));return t.getUTCFullYear()===y&&t.getUTCMonth()===m-1&&t.getUTCDate()===d;}
  function validate(d){
    const errors=[];
    if(!d||typeof d!=='object'||Array.isArray(d)||d.schemaVersion!==1)return ['这不是本站的资料文件，请选择本站导出的 cv.json。'];
    const ids=new Set();
    for(const s of Object.keys(sections)){
      const values=s==='basics'||s==='profile'?[d[s]]:d[s];
      if(!Array.isArray(values)){errors.push(sections[s]+'：缺少资料列表。');continue;}
      if(['work','education'].includes(s)&&!values.length)errors.push(sections[s]+'至少需要一条记录。');
      values.forEach((r,i)=>{
        const prefix=sections[s]+(values.length>1?'第 '+(i+1)+' 条':'');
        if(!r||typeof r!=='object'||Array.isArray(r)){errors.push(prefix+'：资料格式不正确。');return;}
        for(const k of required[s])if(k==='year'? !Number.isInteger(r[k])||r[k]<1000||r[k]>9999:typeof r[k]!=='string'||!r[k].trim())errors.push(prefix+'：请填写有效的'+labels[k]+'。');
        if(s!=='basics'&&s!=='profile'&&s!=='skills'){if(typeof r.id!=='string'||!r.id.trim())errors.push(prefix+'：缺少记录标识，请重新新增记录。');else if(ids.has(r.id))errors.push(prefix+'：记录标识重复。');else ids.add(r.id);}
        for(const k of ['date','startDate','endDate'])if(r[k]&&!validDate(r[k]))errors.push(prefix+'：'+labels[k]+'请使用有效的 YYYY、YYYY-MM 或 YYYY-MM-DD。');
        if(['awards','presentations','teaching'].includes(s)&&typeof r.homepage!=='boolean')errors.push(prefix+'：请设置是否显示在网页列表。');
        if(s==='publications'){
          if(!['preprint','accepted','published'].includes(r.status))errors.push(prefix+'：论文状态不正确。');
          if(['accepted','published'].includes(r.status)&&!r.journal?.trim())errors.push(prefix+'：接收或发表的论文需填写期刊。');
          if(!Array.isArray(r.authors)||!r.authors.length||r.authors.some(a=>!a||typeof a.name!=='string'||!a.name.trim()))errors.push(prefix+'：请按顺序填写作者姓名。');
        }
        if(s==='presentations'&&!['upcoming','past'].includes(r.status))errors.push(prefix+'：报告状态不正确。');
        if(s==='education'&&(!Array.isArray(r.supervisors)||r.supervisors.some(a=>!a?.name?.trim())))errors.push(prefix+'：请填写导师姓名或删除空导师。');
        if(s==='skills'&&(!Array.isArray(r.items)||r.items.some(x=>typeof x!=='string'||!x.trim())))errors.push(prefix+'：请每行填写一项技能。');
      });
    }
    if(d.basics){for(const k of ['email','institutionalEmail'])if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(d.basics[k]||''))errors.push('请填写有效邮箱。');if(!/^\d{4}-\d{4}-\d{4}-[\dX]{4}$/.test(d.basics.orcid||''))errors.push('ORCID 应为 0000-0000-0000-0000 格式。');}
    function links(v){if(!v||typeof v!=='object')return;for(const [k,x] of Object.entries(v)){if(typeof x==='string'&&x&&(k.toLowerCase().endsWith('url')||['website','googleScholar'].includes(k)||k==='arxiv'&&x.includes('://'))){try{const u=new URL(x);if(!['https:','http:'].includes(u.protocol))throw Error();}catch{errors.push((labels[k]||k)+'：请填写完整的 http:// 或 https:// 地址。');}}if(x&&typeof x==='object')links(x);}}
    links(d);return [...new Set(errors)];
  }
  function field(record,key,parent,index){
    if(key==='authors'||key==='supervisors'){people(record,key,parent,index);return;}
    const wrap=node('div',undefined,'field');const id='cv-'+section+'-'+index+'-'+key;const label=node('label',(section==='skills'&&key==='name'?'分类名称':labels[key]||key)+(required[section]?.includes(key)?' *':''));label.htmlFor=id;
    let input;
    if(key==='homepage'){input=node('input');input.type='checkbox';input.checked=record[key]===true;}
    else if(key==='status'||key==='term'){
      input=node('select');const options=key==='term'?{'':'未指定',Spring:'Spring（春季）',Summer:'Summer（夏季）',Fall:'Fall（秋季）',Winter:'Winter（冬季）'}:section==='publications'?{preprint:'预印本',accepted:'已接收',published:'已发表'}:{past:'已完成',upcoming:'即将举行'};
      if(record[key]&&!Object.hasOwn(options,record[key]))options[record[key]]=record[key];
      for(const [v,t] of Object.entries(options)){const o=node('option',t);o.value=v;input.append(o);}input.value=record[key]||'';
    }else if(['researchInterests','industrySummary','summary','note','items'].includes(key)){input=node('textarea');input.value=key==='items'?(record[key]||[]).join('\n'):record[key]||'';wrap.classList.add('wide');}
    else{input=node('input');input.type=key==='year'?'number':'text';input.value=record[key]??'';if(key==='year'){input.min='1000';input.max='9999';}if(['date','startDate','endDate'].includes(key))input.placeholder='2027 或 2027-03 或 2027-03-15';}
    input.id=id;input.addEventListener(key==='homepage'||key==='status'||key==='term'?'change':'input',()=>{record[key]=key==='homepage'?input.checked:key==='year'?(input.value===''?null:Number(input.value)):key==='items'?input.value.split('\n').map(s=>s.trim()).filter(Boolean):input.value;dirty();});wrap.append(label,input);parent.append(wrap);
  }
  function people(record,key,parent,index){
    const box=node('div',undefined,'nested');box.append(node('strong',key==='authors'?'作者（顺序与论文一致）':'导师'));if(!Array.isArray(record[key]))record[key]=[];
    record[key].forEach((p,i)=>{const row=node('div',undefined,'person');for(const k of ['name','url']){const w=node('div',undefined,'field');const label=node('label',k==='name'?'姓名':'网页链接（可不填）');const input=node('input');input.type='text';input.value=p[k]||'';input.id='cv-'+section+'-'+index+'-'+key+'-'+i+'-'+k;label.htmlFor=input.id;input.addEventListener('input',()=>{p[k]=input.value;dirty();});w.append(label,input);row.append(w);}row.append(button('上移',()=>{if(i>0){[record[key][i-1],record[key][i]]=[record[key][i],record[key][i-1]];dirty();render();}}),button('删除',()=>{record[key].splice(i,1);dirty();render();}));box.append(row);});
    box.append(button(key==='authors'?'添加作者':'添加导师',()=>{record[key].push({name:''});dirty();render();}));parent.append(box);
  }
  function title(r,i){return r.title||r.course||r.position||r.degree||r.name||r.role||'新记录 '+(i+1);}
  function render(){
    const root=$('editor-fields');root.replaceChildren();const single=['basics','profile'].includes(section);$('add-record').hidden=single;
    const rows=single?[data[section]]:data[section];
    rows.forEach((r,i)=>{const card=node(single?'div':'details',undefined,'record');if(!single){card.open=i===0;card.append(node('summary',title(r,i)));}const grid=node('div',undefined,'grid');for(const k of schemas[section])field(r,k,grid,i);card.append(grid);
      if(!single){const actions=node('div',undefined,'row-actions');actions.append(button('上移',()=>{if(i){[rows[i-1],rows[i]]=[rows[i],rows[i-1]];dirty();render();}}),button('下移',()=>{if(i<rows.length-1){[rows[i+1],rows[i]]=[rows[i],rows[i+1]];dirty();render();}}),button('删除记录',()=>{if(window.confirm('删除“'+title(r,i)+'”？尚未提交前不会影响线上网站。')){rows.splice(i,1);dirty();render();}}));card.append(actions);}root.append(card);
    });
    if(!rows.length)root.append(node('p','还没有记录，点击“新增记录”开始填写。'));
  }
  async function remote(){const response=await fetch(source+'?t='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('无法读取最新资料（'+response.status+'）');return response.json();}
  async function load(){
    if(changed&&!window.confirm('重新读取会放弃当前未下载的修改，是否继续？'))return;
    busy=true;$('export-cv').disabled=true;message('正在读取最新资料…');
    try{const d=await remote();const errors=validate(d);if(errors.length)throw Error(errors.join('\n'));base=JSON.stringify(d);data=structuredClone(d);changed=false;render();$('editor-section').disabled=false;$('export-cv').disabled=false;$('save-draft').disabled=false;message('已读取最新资料。请选择内容并填写，完成后下载更新文件。');}catch(e){message(e.message+'。可重试，或载入之前下载的资料文件。',true);}finally{busy=false;}
  }
  for(const [v,t] of Object.entries(sections)){const o=node('option',t);o.value=v;$('editor-section').append(o);}$('editor-section').value=section;
  $('editor-section').addEventListener('change',()=>{section=$('editor-section').value;render();});
  $('add-record').addEventListener('click',()=>{const r={};for(const k of schemas[section])r[k]=k==='homepage'?true:['authors','supervisors','items'].includes(k)?[]:k==='year'?new Date().getFullYear():'';if(section!=='skills')r.id=section+'-'+crypto.randomUUID();if(section==='publications'){r.status='preprint';r.authors=[{name:''}];}if(section==='presentations')r.status='past';data[section].unshift(r);dirty();render();});
  $('export-cv').addEventListener('click',async()=>{
    if(busy||!data)return;const errors=validate(data);if(errors.length){message('请先补全或修正以下内容：\n'+errors.join('\n'),true);return;}
    busy=true;$('export-cv').disabled=true;
    try{const latest=await remote();if(base&&JSON.stringify(latest)!==base)throw Error('线上资料已变化。请先保存草稿，再重新读取最新资料并应用改动，避免覆盖其他更新。');download('cv.json');changed=false;message('已下载 cv.json。现在点击“打开 GitHub 上传”，上传该文件并提交到 master。下载本身还没有发布。');}catch(e){message(e.message,true);}finally{busy=false;$('export-cv').disabled=false;}
  });
  $('import-cv').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;if(changed&&!window.confirm('载入文件会替换当前未下载的修改，是否继续？'))return;try{const d=JSON.parse(await f.text());if(!d||d.schemaVersion!==1||!d.basics||!d.profile||Object.keys(sections).filter(s=>!['basics','profile'].includes(s)).some(s=>!Array.isArray(d[s])||d[s].some(r=>!r||typeof r!=='object'||Array.isArray(r))))throw Error('请选择本站导出的更新文件或草稿。');const errors=validate(d);data=d;changed=true;$('editor-section').disabled=false;$('export-cv').disabled=false;$('save-draft').disabled=false;render();message(errors.length?'已载入草稿。完成填写后才能下载正式更新文件：\n'+errors.join('\n'):'已载入文件。请核对内容后下载并上传到 GitHub。',errors.length>0);}catch(err){message('载入失败：'+err.message,true);}e.target.value='';});
  $('save-draft').addEventListener('click',()=>{if(!data)return;download('cv-draft.json');changed=false;message('已保存草稿 cv-draft.json。可稍后载入继续填写；请勿将草稿直接上传到 GitHub。');});
  $('reload-cv').addEventListener('click',load);
  window.addEventListener('beforeunload',e=>{if(changed){e.preventDefault();e.returnValue='';}});
  load();
})();
