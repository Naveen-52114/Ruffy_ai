import os
import google.generativeai as genai

def main():
    print("====================================")
    print("        RuFfy AI Chatbot           ")
    print("====================================")
    
    # Hardcoded API key provided by user
    api_key = "AIzaSyCIEXe5bKzd0ZDt1GZmIbEIgPZ7Qj3pFA8"
    
    if not api_key:
        api_key = input("Please enter your Gemini API key: ").strip()
        if not api_key:
            print("API key is required to use this chatbot.")
            return
            
    try:
        genai.configure(api_key=api_key)
        # Use gemini-2.5-flash as the default model
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Start a chat session to maintain history
        chat = model.start_chat(history=[])
        
        print("\nChatbot initialized! Type 'quit' or 'exit' to end the conversation.\n")
        
        while True:
            user_input = input("You: ")
            
            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break
                
            if not user_input.strip():
                continue
                
            # Send message to Gemini and get response
            response = chat.send_message(user_input)
            print(f"\nGemini: {response.text}\n")
            
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    main()
