import { predictFeedbackMood } from '../citizen-web/src/server/moodPredictor.js';

async function test() {
  try {
    console.log('Starting prediction test...');
    const result = await predictFeedbackMood('This is a test feedback. I am very happy!');
    console.log('Result:', result);
  } catch (error) {
    console.error('Test failed with error:', error);
  }
}

test();
