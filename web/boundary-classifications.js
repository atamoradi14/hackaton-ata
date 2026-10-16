export function numericConfidence(item){
  const score=item?.confidence_score;
  return typeof score==='number'&&Number.isFinite(score)&&score>=0&&score<=1?Math.round(score*100)+'%':'not scored';
}
export function classificationLabel(item){
  if(!item)return 'unresolved';
  const labels={under_0_5_m:'<0.5 m','0_5_to_1_m':'0.5–<1 m','1_to_2_m':'1–<2 m',
    '2_to_3_m':'2–<3 m','3_to_5_m':'3–<5 m','5_to_10_m':'5–<10 m','10_m_or_more':'≥10 m',
    variable_height:'Variable height',occluded_or_unresolved:'Occluded / unresolved',unresolved:'Unresolved',not_applicable:'Not applicable'};
  return labels[item.label]||item.label?.replaceAll('_',' ')||'Unresolved';
}
