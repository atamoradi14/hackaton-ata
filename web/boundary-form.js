// A proposal may seed an unreviewed edit form, never overwrite a saved review.
export function boundaryForm(entity){
  const p=entity.prediction;
  const proposed=!!(!entity.review&&p&&!p.stale&&p.status==='unreviewed_prediction');
  const values=proposed?p:(entity.structure||{});
  return {values,proposed,notes:proposed?
    'Unverified image/LiDAR proposal for review: '+p.rationale:entity.review?.notes||''};
}
