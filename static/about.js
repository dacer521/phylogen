space = document.getElementById("text")

function help() {
    text = "Phylogen is an evolution simulator game; here is how you play it! On the home screen, click one of the 7 biomes. I’ll show an example of the Ocean biome. When you enter the page, you will see 3 buttons, a title, the game board, and a side bar. The side bar gives information about the game, such as average genomes, traits, and numbers of a given species. The game board shows the location of each species and represents a group of that species. To play the game, click the “start movement” button, and watch as evolution unfolds! If you’d like, you can click the “define your own species” button and replace one of the animals with anything you want! That is an overview of how the game works. I hope this helped and please enjoy the game! "
    space.textContent = text
    space.style.display = "block"
}

function info() {

     text = "This game was made for my senior project at Minuteman High School. It was made using the Python library Flask for the back end, html CSS and JavaScript for the front end, and the Python library DEAP for the evolutionary back-end stuff. All of the biomes in this game are ones that could theoretically exist and are modeled after real places, they are as follows: the Ocean is based on the Northeast Pacific Ocean, the Rainforest is modeled after the Neotropical rainforest, the Desert is modeled after Mojave Desert the Tundra modeled after the North American Tundra, the Mountain is modeled after the Montane Rocky Mountains, the  Wetland is modeled after Great Marsh in Massachusetts, and the Forest is modeled after Canadian arctic forest. The code and sources for this project are available on the GitHub page for this project here https://github.com/dacer521/phylogen. "
    space.textContent = text
    space.style.display = "block"

}

function author() {

    text = "Hello! My name is David Manuel. I created this project as my Senior project and I’m hoping to study computational biology in college. This project is something I’ve wanted to do for a long time now, and I’m very glad to finally have done it! I fell in love with programming in elementary school, and biology in 7th grade, so I’m very glad to be able to merge these interests. This project is my “magnum opus” of high school, and I hope you enjoy it!\n\n Special Thanks to Ian Vail for assistance in formatting this idea, Mr. Eric Marshall for being a great mentor, and finally to Hudson Jean and Kyle Rosenstein for making sprites; Hudson did the Ocean and Rainforest sprites and Kyle did the desert sprites. "
    space.textContent = text
    space.style.display = "block"

}
