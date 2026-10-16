import assert from 'node:assert/strict';
import {numericConfidence,classificationLabel} from '../web/boundary-classifications.js';
assert.equal(numericConfidence({confidence_score:.9}),'90%');
assert.equal(numericConfidence({confidence_score:0}),'0%');
assert.equal(numericConfidence({confidence_score:1.2}),'not scored');
assert.equal(classificationLabel({label:'2_to_3_m'}),'2–<3 m');
assert.equal(classificationLabel({label:'variable_height'}),'Variable height');
console.log('PASS: numeric type/height confidence and explicit range/variable class labels');
