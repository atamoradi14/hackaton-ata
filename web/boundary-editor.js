import {boundaryForm} from './boundary-form.js';
const types=['unknown','fence','wall','retaining_wall','gate','hedge','vegetation','mixed','building','bund','kerb','other'];
export async function boundaryEditor({job,api,onChange,onSelect}){
  const root=document.getElementById('boundary-editor');
  root.innerHTML=`<legend>Property lines & objects</legend><label><input id="be-visible" type="checkbox" checked> Selectable 3D boundary lines</label><label><input id="be-labels" type="checkbox" checked> Edge numbers</label><p>Click a numbered line in either 3D view, or choose it below. These are cadastral positions, not measured fences.</p><label for="be-choice">Boundary / object</label><select id="be-choice" aria-label="Boundary or object"></select><div class="be-downloads"><a id="be-json">Property JSON</a><a id="be-geojson">Edges GeoJSON</a></div><small id="be-loading">Loading boundary records…</small><section id="be-detail" hidden><h2 id="be-title"></h2><small id="be-facts"></small><details id="be-prediction"><summary>Assistant prediction · unverified</summary><p id="be-pred-summary"></p><pre id="be-pred-json"></pre><button id="be-copy" type="button">Copy proposal into edit form</button></details><details><summary>Edit selected entity</summary><form id="be-form"><div class="be-grid"><label>Type<select id="be-type">${types.map(t=>`<option>${t}</option>`).join('')}</select></label><label>Material<input id="be-material" maxlength="100" placeholder="Unknown"></label>${['height','width','depth'].map(k=>`<label>${k[0].toUpperCase()+k.slice(1)} (m)<input id="be-${k}" type="number" min="0" max="100" step="any" placeholder="Unknown"></label>`).join('')}<label>Continuity<select id="be-continuity"><option>unknown</option><option>continuous</option><option>discontinuous</option></select></label><label>Permeability<select id="be-permeability"><option>unknown</option><option>solid</option><option>partly_permeable</option><option>permeable</option></select></label><label>Potential influence<select id="be-influence"><option>uncertain</option><option>block</option><option>divert</option><option>constrict</option><option>channel</option><option>negligible</option></select></label></div><label>Evidence / review note<textarea id="be-note" required minlength="5" maxlength="1200"></textarea></label><button id="be-save">Save entity review</button><small id="be-saved" role="status"></small></form></details><details><summary>Endpoints, linked objects & source evidence</summary><pre id="be-evidence"></pre></details></section>`;
  const $=id=>document.getElementById('be-'+id);
  const formSource=document.createElement('small');formSource.id='be-form-source';$('form').prepend(formSource);
  const advanced=document.createElement('details'),advancedTitle=document.createElement('summary');advancedTitle.textContent='Ranges, method & native statistics';$('pred-json').before(advanced);advanced.append(advancedTitle,$('pred-json'));
  const fieldReview=document.createElement('div');fieldReview.id='be-field-review';advanced.before(fieldReview);
  function proposalSummary(p){
    const prefix=p.stale?'OUTDATED EVIDENCE · ':'';
    if(!p.field_assessments)return `${prefix}${p.type||'unknown'} · ${p.height_m==null?'height unknown':p.height_m+' m estimate'} · ${p.confidence} confidence (uncalibrated). ${p.rationale}`;
    return `${prefix}${p.type} · type confidence: ${p.field_assessments.type.confidence}. ${p.height_m==null?'Height unknown':p.height_m+' m estimate · height confidence: '+p.field_assessments.height_m.confidence}. Unverified; confidence is uncalibrated.`;
  }
  function showFieldReview(prediction){
    fieldReview.replaceChildren();
    if(!prediction.field_assessments)return;
    const review=controller.record.prediction_bundle?.visual_review;
    const note=document.createElement('p');note.textContent=`Visibility: ${prediction.visual_review?.visibility?.replaceAll('_',' ')||'unknown'}.`;
    const fields=document.createElement('dl');fields.className='be-field-assessments';
    for(const key of ['type','height_m','material','continuity','width_m','depth_m','permeability','crossed_by_flow_path','potential_influence','risk_level']){
      const assessment=prediction.field_assessments[key];if(!assessment)continue;
      const title=document.createElement('dt'),detail=document.createElement('dd');
      title.textContent=key.replaceAll('_',' ');
      let value=prediction[key];if(value==null||value==='unknown'||value==='uncertain')value='Unknown / not assessed';else if(typeof value==='boolean')value=value?'Yes — mapped GIS crossing':'No proper mapped GIS crossing';else value=String(value).replaceAll('_',' ')+(key.endsWith('_m')?' m':'');
      detail.textContent=`${value} · ${assessment.confidence.replaceAll('_',' ')}. ${assessment.basis}`;fields.append(title,detail);
    }fieldReview.append(note,fields);
    const observation=document.createElement('details'),observationTitle=document.createElement('summary'),observationText=document.createElement('p');observationTitle.textContent='Visual observations & confidence change';observationText.textContent=prediction.rationale+' '+(prediction.visual_review?.observation||'')+' '+(prediction.confidence_change?.reason||'');observation.append(observationTitle,observationText);fieldReview.append(observation);
    const sourceList=document.createElement('div');
    for(const source of review?.sources||[]){
      if(!prediction.visual_review?.source_ids?.includes(source.id))continue;
      if(source.source_kind==='user_attachment'){
        const label=document.createElement('small');label.textContent=`User image ${source.attachment_index} · ${source.view_direction_label||source.view} · ${source.imagery_date||'date unverified'}${source.identity_status==='probable_visual_match'?' · property match provisional':''}`;sourceList.append(label);continue;
      }
      let url;try{url=new URL(source.url);}catch{continue;}
      if(url.protocol!=='https:'||!['earth.google.com','www.google.com','maps.google.com'].includes(url.hostname))continue;
      const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=`${source.provider} · ${source.view.replaceAll('_',' ')} · ${source.imagery_date||'date unverified'}`;sourceList.append(link);
    }fieldReview.append(sourceList);
    if(prediction.components?.length){const title=document.createElement('h3');title.textContent='Objects along this boundary';fieldReview.append(title);for(const component of prediction.components){const text=document.createElement('p');text.textContent=`${component.type.replaceAll('_',' ')} · ${component.position_note||'position unresolved'} · ${component.confidence||'low'} confidence. ${component.notes||''}`;fieldReview.append(text);}}
    const limitation=document.createElement('small');limitation.textContent=review?.limitation||'';fieldReview.append(limitation);
  }
  const evidenceDialog=document.createElement('dialog'),closeEvidence=document.createElement('button'),evidenceImage=document.createElement('img');evidenceDialog.id='be-evidence-dialog';closeEvidence.textContent='Close evidence';closeEvidence.type='button';closeEvidence.onclick=()=>evidenceDialog.close();evidenceImage.alt='Recorded aerial and native LiDAR evidence with numbered property edges';evidenceDialog.append(closeEvidence,evidenceImage);document.body.append(evidenceDialog);
  const controller={record:null,selected:null,kind:'segment',visible:true,labels:true};
  controller.select=(id,kind='segment')=>{
    const list=kind==='segment'?controller.record.boundary_segments:[...controller.record.objects,...controller.record.prediction_objects];
    const entity=list.find(v=>v.id===id);if(!entity)return;
    controller.selected=entity;controller.kind=kind;controller.visible=true;$('visible').checked=true;$('choice').value=kind+':'+id;$('detail').hidden=false;
    const index=controller.record.boundary_segments.indexOf(entity);$('title').textContent=kind==='segment'?'Boundary edge '+(index+1):(entity.prediction?.type||entity.source_id||'Object');
    $('facts').textContent=kind==='segment'?`${entity.length_m.toFixed(2)} m · mapped flow: ${entity.flow_path.relation} · ${entity.lidar.usable_return_count??'?'} usable nearby returns`:`${entity.source_id} · ${entity.source_feature_id||entity.id}`;
    $('evidence').textContent=JSON.stringify(entity,null,2);$('saved').textContent='';
    const prediction=entity.prediction;$('prediction').hidden=!prediction;
    showFieldReview(prediction||{});
    if(prediction){$('pred-summary').textContent=proposalSummary(prediction);$('pred-json').textContent=JSON.stringify(prediction,null,2);$('copy').disabled=prediction.stale||prediction.status==='not_applicable';$('prediction').open=true;let imageLink=$('image');if(!imageLink){imageLink=document.createElement('a');imageLink.id='be-image';imageLink.textContent='View the recorded aerial / LiDAR evidence';imageLink.onclick=e=>{e.preventDefault();evidenceImage.src=imageLink.href;evidenceDialog.showModal();};$('prediction').append(imageLink);}imageLink.href=`/api/properties/${controller.record.id}/prediction-evidence`;}
    const form=boundaryForm(entity),s=form.values;$('type').value=types.includes(s.type)?s.type:'unknown';$('material').value=s.material||'';for(const k of ['height','width','depth']){$(k).value=s[k+'_m']??'';$(k).placeholder=form.proposed?'Unresolved':'Unknown';$(k).title=form.proposed?(s.field_assessments?.[k+'_m']?.basis||'Unverified proposal; inspect evidence'):'';}$('continuity').value=s.continuity||'unknown';$('permeability').value=s.permeability||'unknown';$('influence').value=s.potential_influence||'uncertain';$('note').value=form.notes;formSource.textContent=form.proposed?'UNSAVED IMAGE/LiDAR PROPOSAL · review before saving. Unresolved dimensions are not zero.':entity.review?'Saved manual review values.':'No fresh proposal or saved review.';if(form.proposed)$('saved').textContent='Prefilled from an unverified proposal. Not saved as a manual review; unresolved fields remain explicit.';
    onSelect(controller);
  };
  controller.refresh=value=>{controller.record=value;$('choice').replaceChildren();const add=(kind,entity,text)=>{const o=document.createElement('option');o.value=kind+':'+entity.id;o.textContent=text;$('choice').append(o);};
    value.boundary_segments.forEach((e,i)=>add('segment',e,`Edge ${i+1} · ${e.structure.type==='unknown'?(e.prediction?.type&&e.prediction.type!=='unknown'?'possible '+e.prediction.type:'unknown'):e.structure.type} · ${e.length_m.toFixed(1)} m`));
    for(const o of [...value.objects,...value.prediction_objects]){if(o.prediction?.alias_of)continue;add('object',o,(o.prediction?.type||o.source_id)+' · '+(o.source_feature_id||o.id.slice(-8)));}
    onChange(controller);
  };
  $('choice').onchange=e=>{const [kind,id]=e.target.value.split(':');controller.select(id,kind);};
  for(const k of ['visible','labels'])$(k).onchange=e=>{controller[k]=e.target.checked;onSelect(controller);};
  $('copy').onclick=()=>{const p=controller.selected?.prediction;if(!p||p.stale)return;$('type').value=types.includes(p.type)?p.type:'unknown';$('material').value=p.material||'';for(const k of ['height','width','depth'])$(k).value=p[k+'_m']??'';for(const k of ['continuity','permeability','influence'])$(k).value=p[k==='influence'?'potential_influence':k]||(k==='influence'?'uncertain':'unknown');$('note').value='Review of unverified assistant proposal: '+p.rationale;$('form').closest('details').open=true;$('saved').textContent='Not saved. Check the evidence, correct the proposal and add your review note.';};
  $('form').onsubmit=async e=>{e.preventDefault();const entity=controller.selected,kind=controller.kind,pid=controller.record.id;$('save').disabled=true;
    try{const body={type:$('type').value,material:$('material').value.trim()||null,continuity:$('continuity').value,permeability:$('permeability').value,potential_influence:$('influence').value,notes:$('note').value,risk_level:entity.risk?.level||null};for(const k of ['height','width','depth'])body[k+'_m']=$(k).value===''?null:Number($(k).value);
      const value=await api(`/api/properties/${pid}/${kind==='segment'?'segments':'objects'}/${entity.id}/review`,body);
      const current=controller.selected.id,currentKind=controller.kind;controller.refresh(value);controller.select(current,currentKind);$('saved').textContent='Saved locally. Manual review and assistant prediction remain separate; not field verified.';
    }catch(error){$('saved').textContent=error.message;}finally{$('save').disabled=false;}
  };
  try{const value=await api(`/api/jobs/${job}/property`);controller.refresh(value);$('json').href=`/api/properties/${value.id}/export`;$('json').download=value.id+'.json';$('geojson').href=`/api/properties/${value.id}/boundaries`;$('geojson').download=value.id+'-boundaries.geojson';$('loading').textContent=`${value.boundary_segments.length} individual edges · ${value.prediction_bundle?'saved sample predictions':'no assistant sample for this property'}`;controller.select(value.boundary_segments[0].id);}
  catch(error){$('loading').textContent='Boundary records: '+error.message;}
  return controller;
}
