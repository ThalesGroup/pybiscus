
class CircularBuffer {
    constructor(maxSize = 30) {
        this.items = [];
        this.maxSize = maxSize;
    }

    add(item) {
        this.items.push(item);
        while (this.items.length > this.maxSize) {
            this.items.shift();
        }
    }

    get length() {
        return this.items.length;
    }

    get all() {
        return [...this.items]; // Returns a copy in order to avoid external modifications
    }

    get latest() {
        return this.items[this.items.length - 1];
    }

    get oldest() {
        return this.items[0];
    }

    clear() {
        this.items = [];
    }

    isFull() {
        return this.items.length >= this.maxSize;
    }

    isEmpty() {
        return this.items.length === 0;
    }

    getAt(index) {
        return this.items[index];
    }

    // Iterator to use with for...of
    *[Symbol.iterator]() {
        for (const item of this.items) {
            yield item;
        }
    }
}

class Session {
    constructor() {
        this.sessionState = "paramsUndefined";
        this.agentStates = {}; // dict : agentName -> state
        this.roundNumber = 0;
        this.intervalIds = []; // Array to store all interval IDs
    }

    getAgentState(agentName) {
        if (!(agentName in this.agentStates)) {
            this.agentStates[agentName] = "declared";
        }
        return this.agentStates[agentName];
    }

    setAgentState(agentName, state) {
        this.agentStates[agentName] = state;
        
        // If state is "terminated", check if all agents are terminated
        if (state === "terminated") {
            const allTerminated = Object.values(this.agentStates).every(agentState => agentState === "terminated");
            if (allTerminated) {
                this.stopSession();
            }
        }
    }
    
    // Start a callback with periodic function execution
    startCallback(func, duration = 5000) {
        // Execute the function immediately
        func();
        
        // Set up interval and store its ID
        const intervalId = setInterval(func, duration);
        this.intervalIds.push(intervalId);
        
        return intervalId;
    }

    // Stop all intervals and end the session
    stopSession() {
        // Clear all stored intervals
        this.intervalIds.forEach(intervalId => {
            clearInterval(intervalId);
        });
        
        // Reset the intervals array
        this.intervalIds = [];
        
        // update session state
        this.sessionState = "sessionCompleted";
    }
}
